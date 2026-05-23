# backend/shared/documents/pdf_layout_parser.py
# Feladat: PDF dokumentumok layout alapú szövegkinyerését végzi pdfplumber segítségével. Oldalszéli zajt, ismétlődő fejléc/lábléc sorokat, headingeket, listákat, táblázatszerű sorokat és oldaltörésen átnyúló bekezdéseket heuristikusan csoportosít ExtractedParagraph blokkokká. Shared PDF utility, néhány jogi/magyar dokumentumokra hangolt heurisztikával.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

import io
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, replace
from statistics import median
from typing import Any

from shared.documents.models import ExtractedDocument, ExtractedParagraph

_EDGE_MARGIN = 42.0
_LINE_TOP_TOLERANCE = 3.0
_PARAGRAPH_GAP_MIN = 6.0
_PARAGRAPH_BLOCK_BREAK_MIN = 18.0
_PARAGRAPH_BLOCK_BREAK_RATIO = 1.9
_INDENT_BLOCK_BREAK_MIN = 26.0
_HEADER_FONT_RATIO = 1.18
_HEADER_MAX_WORDS = 18
_NUMERIC_LIST_PATTERN = re.compile(
    r"^\s*(?:[a-z]\s+)?((?:\d+|[A-Z])(?:\.(?:\d+|[A-Z])){0,5}\.)\s+([A-Za-zÁÉÍÓÖŐÚÜŰáéíóöőúüű0-9].*)$"
)


@dataclass(frozen=True)
class _PdfLine:
    text: str
    page_number: int
    x0: float
    top: float
    x1: float
    bottom: float
    font_size: float
    is_bold: bool
    page_height: float
    word_count: int
    wide_gap_count: int
    max_gap: float
    cell_texts: tuple[str, ...] = ()


def _normalize_inline_text(text: str) -> str:
    normalized = re.sub(r"\s+", " ", text or "").strip()
    normalized = re.sub(r"\s+([,.;:!?%\)\]\}])", r"\1", normalized)
    normalized = re.sub(r"([\(\[\{])\s+", r"\1", normalized)
    return normalized


def _normalize_repeat_key(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _match_numeric_list_marker(text: str) -> re.Match[str] | None:
    return _NUMERIC_LIST_PATTERN.match(text or "")


def _looks_like_list_item(text: str) -> bool:
    value = text or ""
    if re.match(r"^\s*[-*•]\s+\S+", value):
        return True
    return _match_numeric_list_marker(value) is not None


def _starts_forced_marker_break(text: str) -> bool:
    value = text or ""
    if re.match(r"^\s*[-–—]\s+\S+", value):
        return True
    if re.match(r"(?i)^\s*[ivxlcdm]+[.,]\s+\S+", value):
        return True
    return bool(re.match(r"^\s*(?:\d+|[A-Z])(?:\.(?:\d+|[A-Z])){0,5}[.,]\s+\S+", value))


def _looks_like_legal_section_heading(text: str) -> bool:
    value = text or ""
    return bool(re.match(r"^\s*\d+\.[A-Z]\.\s+\S+", value))


def _has_likely_sentence_verb(text: str) -> bool:
    value = _normalize_inline_text(text)
    if not value:
        return False
    lowered = value.lower()
    if any(
        token in lowered
        for token in (
            " van ",
            " volt ",
            " lesz ",
            " lehet ",
            " kell ",
            " jogosult",
            " köteles",
            " alkalmazandó",
            " minősül",
            " tartalmaz",
            " jelenti",
            " történ",
            " módosíthat",
            " fizet",
            " köt ",
            " nyújt",
            " biztosít",
        )
    ):
        return True
    return bool(
        re.search(
            r"\b\w+(?:ik|dik|odik|edik|het|ható|hető|tat|tet|ja|i|ta|te|nak|nek)\b",
            lowered,
            flags=re.UNICODE,
        )
    )


def _is_title_case_like(text: str) -> bool:
    words = re.findall(r"\b[A-Za-zÁÉÍÓÖŐÚÜŰáéíóöőúüű0-9][\wÁÉÍÓÖŐÚÜŰáéíóöőúüű.-]*\b", text, flags=re.UNICODE)
    if not words or len(words) > 12:
        return False
    significant = [word for word in words if len(word) > 2]
    if not significant:
        significant = words
    uppercase_like = sum(1 for word in significant if word[:1].isupper() or word[:1].isdigit())
    return uppercase_like >= max(1, len(significant) - 1)


def _looks_like_edge_pagination(line: _PdfLine) -> bool:
    normalized = _normalize_repeat_key(line.text)
    if not normalized:
        return False
    near_edge = line.top <= _EDGE_MARGIN or (line.page_height - line.bottom) <= _EDGE_MARGIN
    if not near_edge:
        return False
    patterns = (
        r"^\d+\s*[./-]?\s*oldal$",
        r"^oldal\s*\d+$",
        r"^page\s*\d+$",
        r"^\d+\s*/\s*\d+$",
        r"^\d+$",
    )
    return any(re.match(pattern, normalized) for pattern in patterns)


def _join_word_tokens(words: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    previous_x1: float | None = None
    for word in words:
        token = str(word.get("text") or "").strip()
        if not token:
            continue
        x0 = float(word.get("x0") or 0.0)
        add_space = bool(parts)
        if previous_x1 is not None and x0 - previous_x1 > 9.0:
            add_space = True
        if token[:1] in ",.;:!?%)]}":
            add_space = False
        if add_space:
            parts.append(" ")
        parts.append(token)
        previous_x1 = float(word.get("x1") or x0)
    return _normalize_inline_text("".join(parts))


def _measure_word_gaps(words: list[dict[str, Any]]) -> tuple[int, float]:
    wide_gap_count = 0
    max_gap = 0.0
    previous_x1: float | None = None
    for word in words:
        x0 = float(word.get("x0") or 0.0)
        if previous_x1 is not None:
            gap = max(0.0, x0 - previous_x1)
            max_gap = max(max_gap, gap)
            if gap >= 28.0:
                wide_gap_count += 1
        previous_x1 = float(word.get("x1") or x0)
    return wide_gap_count, max_gap


def _split_words_into_cells(words: list[dict[str, Any]]) -> tuple[str, ...]:
    cells: list[list[dict[str, Any]]] = []
    current_cell: list[dict[str, Any]] = []
    previous_x1: float | None = None
    for word in words:
        token = str(word.get("text") or "").strip()
        if not token:
            continue
        x0 = float(word.get("x0") or 0.0)
        if previous_x1 is not None and x0 - previous_x1 >= 28.0 and current_cell:
            cells.append(current_cell)
            current_cell = []
        current_cell.append(word)
        previous_x1 = float(word.get("x1") or x0)
    if current_cell:
        cells.append(current_cell)
    return tuple(
        cell_text
        for cell in cells
        if (cell_text := _join_word_tokens(cell))
    )


def _looks_like_table_of_contents_header(text: str) -> bool:
    normalized = _normalize_repeat_key(text)
    return normalized in {"tartalomjegyzék", "contents", "table of contents"}


def _looks_like_table_of_contents_entry(text: str) -> bool:
    value = _normalize_inline_text(text)
    if not value:
        return False
    return bool(
        re.match(
            r"^(?:\d+(?:\.\d+){0,5}\.?\s+)?[A-Za-zÁÉÍÓÖŐÚÜŰáéíóöőúüű0-9].*\.{2,}\s*\d+$",
            value,
        )
    )


def _looks_like_short_metadata_line(text: str) -> bool:
    value = _normalize_inline_text(text)
    if not value:
        return False
    if re.match(
        r"^(?:kelt|hatályos|verzió|kiadás|melléklet|ikt\.?|ügyiratszám|készítette|készítve|frissítve|dátum|oldal|page)\s*[:\-]",
        value,
        flags=re.IGNORECASE,
    ):
        return True
    # Melléklet / függelék címke kettőspont nélkül (PDF gyakori)
    if re.match(
        r"^\s*(?:\d+\.\s*)?(?:számú\s+)?(?:melléklet|függelék|annex|appendix)\b",
        value,
        flags=re.IGNORECASE,
    ):
        return True
    if ":" in value:
        key_part = value.split(":", 1)[0].strip()
        if re.fullmatch(r"\d{1,2}", key_part):
            return False
        if re.fullmatch(r"\d{1,2}[:.]\d{2}", value.split(None, 1)[0]):
            return False
        return (
            len(re.findall(r"\b\w+\b", key_part, flags=re.UNICODE)) <= 4
            and len(value) <= 90
            and bool(re.search(r"[A-Za-zÁÉÍÓÖŐÚÜŰáéíóöőúüű]", key_part))
        )
    return False


def _looks_like_place_date_stamp_line(text: str) -> bool:
    """Keltezés / hely + dátum egy sorban — ne olvadjon össze az előző bekezdéssel oldaltörésnél."""
    value = _normalize_inline_text(text)
    if not value or len(value) > 130:
        return False
    if re.match(r"^(?:19|20)\d{2}\.\s*(?:\d{1,2}\.\s*){1,2}\d{0,2}\.?\s*$", value):
        return True
    # Hely, év. hó nap. / Hely, év. MM. DD. (tipikus jogi keltezés)
    if re.match(
        r"^[A-ZÁÉÍÓÖŐÚÜŰ][^,]{0,52},\s*(?:19|20)\d{2}\.(?:\s*\d{1,2}\.){1,2}",
        value,
    ):
        return len(re.findall(r"\b\w+\b", value, flags=re.UNICODE)) <= 16
    if re.match(
        r"^[A-ZÁÉÍÓÖŐÚÜŰ][^,]{0,52},\s*(?:19|20)\d{2}\.\s*"
        r"(?:január|február|március|április|május|június|július|augusztus|szeptember|október|november|december)\s+\d{1,2}",
        value,
        flags=re.IGNORECASE,
    ):
        return True
    return False


def _looks_like_lonely_clause_number_line(text: str) -> bool:
    """Csak számozás egy sorban (pl. \"3.\" vagy \"4.2.\") — PDF-ben gyakran külön sorba tördelődik."""
    return bool(re.match(r"^\s*\d+(?:\.\d+)*\.\s*$", _normalize_inline_text(text)))


def _looks_like_noise_line(text: str) -> bool:
    value = (text or "").strip()
    if not value:
        return True
    if _looks_like_lonely_clause_number_line(value):
        return False
    if re.fullmatch(r"[\W\d_]+", value, flags=re.UNICODE):
        return True
    if len(value) <= 40 and value.count(".") >= 6 and len(re.findall(r"\b\w+\b", value, flags=re.UNICODE)) <= 2:
        return True
    alpha_count = len(re.findall(r"[A-Za-zÁÉÍÓÖŐÚÜŰáéíóöőúüű]", value))
    return alpha_count == 0 and len(value) <= 60


def _looks_like_heading_by_shape(text: str) -> bool:
    value = _normalize_inline_text(text)
    if not value:
        return False
    words = re.findall(r"\b\w+\b", value, flags=re.UNICODE)
    if not words or len(words) > _HEADER_MAX_WORDS or len(value) > 160:
        return False
    if _looks_like_short_metadata_line(value) or _looks_like_noise_line(value):
        return False
    if value.endswith((".", ";")):
        return False
    if _looks_like_legal_section_heading(value):
        return True
    if _is_title_case_like(value):
        return True
    if value.upper() == value and len(words) <= 10:
        return True
    return len(words) <= 8 and not _has_likely_sentence_verb(value)


def _looks_like_table_header_cells(cells: tuple[str, ...]) -> bool:
    normalized_cells = [cell.strip() for cell in cells if cell.strip()]
    if len(normalized_cells) < 2:
        return False
    if any(len(cell) > 40 for cell in normalized_cells):
        return False
    digit_heavy_count = sum(any(char.isdigit() for char in cell) for cell in normalized_cells)
    return digit_heavy_count <= max(1, len(normalized_cells) // 3)


def _looks_like_table_row_line(line: _PdfLine) -> bool:
    cells = tuple(cell.strip() for cell in line.cell_texts if str(cell).strip())
    if len(cells) < 2:
        return False
    if _looks_like_list_item(line.text):
        return False
    if _looks_like_table_header_cells(cells):
        return True
    if len(cells) >= 3:
        return True
    normalized_text = _normalize_inline_text(line.text)
    if len(cells) == 2 and _has_likely_sentence_verb(normalized_text):
        return False
    if len(cells) == 2 and normalized_text.endswith((".", "!", "?")):
        return False
    return line.max_gap >= 72.0 or line.wide_gap_count >= 2


def _group_words_into_lines(words: list[dict[str, Any]], *, page_number: int, page_height: float) -> list[_PdfLine]:
    if not words:
        return []

    ordered_words = sorted(words, key=lambda item: (round(float(item.get("top") or 0.0), 1), float(item.get("x0") or 0.0)))
    lines: list[list[dict[str, Any]]] = []
    current_words: list[dict[str, Any]] = []
    current_top: float | None = None

    for word in ordered_words:
        top = float(word.get("top") or 0.0)
        if current_top is None or abs(top - current_top) <= _LINE_TOP_TOLERANCE:
            current_words.append(word)
            current_top = top if current_top is None else (current_top + top) / 2.0
            continue
        lines.append(current_words)
        current_words = [word]
        current_top = top

    if current_words:
        lines.append(current_words)

    extracted: list[_PdfLine] = []
    for line_words in lines:
        text = _join_word_tokens(line_words)
        if not text:
            continue
        sizes = [float(item.get("size") or 0.0) for item in line_words if float(item.get("size") or 0.0) > 0]
        font_names = [str(item.get("fontname") or "") for item in line_words]
        bold_hits = sum(1 for font_name in font_names if any(token in font_name.lower() for token in ("bold", "black", "semibold", "demi")))
        wide_gap_count, max_gap = _measure_word_gaps(line_words)
        cell_texts = _split_words_into_cells(line_words)
        extracted.append(
            _PdfLine(
                text=text,
                page_number=page_number,
                x0=min(float(item.get("x0") or 0.0) for item in line_words),
                top=min(float(item.get("top") or 0.0) for item in line_words),
                x1=max(float(item.get("x1") or 0.0) for item in line_words),
                bottom=max(float(item.get("bottom") or 0.0) for item in line_words),
                font_size=median(sizes) if sizes else 0.0,
                is_bold=bold_hits >= max(1, len(font_names) // 2),
                page_height=page_height,
                word_count=len([item for item in line_words if str(item.get("text") or "").strip()]),
                wide_gap_count=wide_gap_count,
                max_gap=max_gap,
                cell_texts=cell_texts,
            )
        )
    return extracted


def _detect_repeated_edge_lines(lines: list[_PdfLine]) -> set[tuple[int, str]]:
    positions: defaultdict[str, list[_PdfLine]] = defaultdict(list)
    for line in lines:
        key = _normalize_repeat_key(line.text)
        if len(key) < 3:
            continue
        positions[key].append(line)

    excluded: set[tuple[int, str]] = set()
    for key, occurrences in positions.items():
        if len(occurrences) < 2:
            continue
        near_edge = all(
            line.top <= _EDGE_MARGIN or (line.page_height - line.bottom) <= _EDGE_MARGIN
            for line in occurrences
        )
        if not near_edge:
            continue
        # Hosszabb, mondatos ismétlődés kétszer az él közelében: ne dobjuk ki (lábléc vs. törzsszöveg keveredés).
        wordish = len(re.findall(r"\b\w+\b", key, flags=re.UNICODE))
        short_banner_like = len(key) <= 52 and wordish <= 9
        if len(occurrences) >= 3 or (len(occurrences) >= 2 and short_banner_like):
            for line in occurrences:
                excluded.add((line.page_number, key))
    return excluded


def _is_header(line: _PdfLine, *, baseline_font_size: float) -> bool:
    words = re.findall(r"\b\w+\b", line.text, flags=re.UNICODE)
    if not words:
        return False
    short_enough = len(words) <= _HEADER_MAX_WORDS and len(line.text) <= 160
    emphasized = (line.font_size >= baseline_font_size * _HEADER_FONT_RATIO) or (line.is_bold and len(words) <= 14)
    terminal_punctuation = line.text.endswith((".", ";", ":"))
    if _looks_like_list_item(line.text) and not (_looks_like_legal_section_heading(line.text) and emphasized):
        return False
    return short_enough and (emphasized or _looks_like_heading_by_shape(line.text)) and not terminal_punctuation


def _looks_like_weak_heading_continuation(
    previous_line: _PdfLine,
    line: _PdfLine,
    *,
    baseline_font_size: float,
) -> bool:
    value = _normalize_inline_text(line.text)
    words = re.findall(r"\b\w+\b", value, flags=re.UNICODE)
    if not words:
        return False
    if _looks_like_legal_section_heading(value):
        return False
    similar_font_size = line.font_size <= max(previous_line.font_size * 1.1, baseline_font_size * 1.12)
    strong_font_jump = line.font_size >= max(previous_line.font_size * 1.16, baseline_font_size * _HEADER_FONT_RATIO)
    strong_bold_jump = line.is_bold and not previous_line.is_bold and len(words) <= 10
    sentence_like = _has_likely_sentence_verb(value) or len(words) >= 6
    return similar_font_size and not strong_font_jump and not strong_bold_jump and sentence_like


def _line_block_type(line: _PdfLine, *, baseline_font_size: float) -> str:
    if _looks_like_table_of_contents_header(line.text) or _looks_like_table_of_contents_entry(line.text):
        return "metadata"
    if _looks_like_lonely_clause_number_line(line.text):
        return "list_item"
    if _looks_like_legal_section_heading(line.text) and _is_header(line, baseline_font_size=baseline_font_size):
        return "heading"
    if _looks_like_list_item(line.text):
        return "list_item"
    if _looks_like_table_row_line(line) or re.search(r"\s+\|\s+", line.text):
        return "table_row"
    if _is_header(line, baseline_font_size=baseline_font_size):
        return "heading"
    return "paragraph"


def _starts_new_list_item(text: str) -> bool:
    return _looks_like_list_item(text)


def _ends_with_continuation_mark(text: str) -> bool:
    """Kötőjel / gondolatjel / ellipszis a sor végén — a következő sor gyakran ugyanahhoz a mondatgondolathoz tartozik."""
    t = (text or "").rstrip()
    if not t:
        return False
    if t.endswith("-"):
        return True
    if t[-1] in "\u2013\u2014":  # en dash, em dash
        return True
    if t.endswith("…"):
        return True
    if len(t) >= 3 and t.endswith("..."):
        return True
    return False


def _is_clear_paragraph_break(vertical_gap: float, *, font_size: float) -> bool:
    return vertical_gap > max(_PARAGRAPH_BLOCK_BREAK_MIN, font_size * _PARAGRAPH_BLOCK_BREAK_RATIO)


def _is_clear_indent_break(previous_line: _PdfLine, line: _PdfLine) -> bool:
    return abs(line.x0 - previous_line.x0) >= _INDENT_BLOCK_BREAK_MIN


def _looks_like_empty_line_gap(previous_line: _PdfLine, line: _PdfLine) -> bool:
    if line.page_number != previous_line.page_number:
        return False
    vertical_gap = line.top - previous_line.bottom
    return vertical_gap > max(_PARAGRAPH_BLOCK_BREAK_MIN, previous_line.font_size * 1.8)


def _is_soft_wrap_continuation(
    previous_line: _PdfLine,
    current_type: str,
    line: _PdfLine,
    line_type: str,
    *,
    vertical_gap: float,
    baseline_font_size: float,
) -> bool:
    if current_type not in {"paragraph", "list_item"}:
        return False
    if line_type not in {"paragraph", "list_item", "heading"}:
        return False
    previous_text = previous_line.text.rstrip()
    next_text = (line.text or "").lstrip()
    if not previous_text or not next_text:
        return False
    previous_has_terminal_punctuation = previous_text.endswith((".", ";", ":", "!", "?"))
    if _starts_new_list_item(next_text) and current_type == "list_item":
        return False
    gap_limit = max(_PARAGRAPH_GAP_MIN, previous_line.font_size * 1.1)
    if _ends_with_continuation_mark(previous_text):
        gap_limit = max(
            gap_limit,
            _PARAGRAPH_BLOCK_BREAK_MIN + 2.0,
            previous_line.font_size * (_PARAGRAPH_BLOCK_BREAK_RATIO + 0.35),
        )
    elif (
        line_type == "heading"
        and not previous_has_terminal_punctuation
        and _looks_like_weak_heading_continuation(previous_line, line, baseline_font_size=baseline_font_size)
    ):
        gap_limit = max(
            gap_limit,
            _PARAGRAPH_BLOCK_BREAK_MIN,
            previous_line.font_size * (_PARAGRAPH_BLOCK_BREAK_RATIO + 0.1),
        )
    if vertical_gap > gap_limit:
        return False

    next_first = next_text[:1]
    previous_ends_hyphen = previous_text.endswith("-")
    next_starts_softly = next_first.islower() or next_text.lower().startswith(
        ("és ", "vagy ", "illetve ", "valamint ", "vagyis ", "de ", "azonban ")
    )
    modest_indent_shift = abs(line.x0 - previous_line.x0) <= 42.0

    if line_type == "heading":
        if _looks_like_legal_section_heading(next_text) and _is_header(line, baseline_font_size=baseline_font_size):
            return False
        if previous_ends_hyphen:
            return True
        if _ends_with_continuation_mark(previous_text):
            return modest_indent_shift
        if (
            not previous_has_terminal_punctuation
            and _looks_like_weak_heading_continuation(previous_line, line, baseline_font_size=baseline_font_size)
        ):
            return modest_indent_shift
        return False

    if previous_ends_hyphen:
        return True
    if _ends_with_continuation_mark(previous_text):
        return modest_indent_shift
    if not previous_has_terminal_punctuation and next_starts_softly and modest_indent_shift:
        return True
    if current_type == "list_item" and line_type == "paragraph" and modest_indent_shift:
        return True
    return False


def _last_line_incomplete_for_page_flow(lines: list[_PdfLine]) -> bool:
    """True if the last line likely continues on the next page (no sentence end, or hyphen wrap)."""
    if not lines:
        return False
    t = lines[-1].text.rstrip()
    if not t:
        return False
    if _ends_with_continuation_mark(t):
        return True
    return not t.endswith((".", ";", ":", "!", "?"))


def _should_merge_pdf_across_page_break(
    *,
    current_lines: list[_PdfLine],
    current_type: str,
    previous_line: _PdfLine,
    line: _PdfLine,
    line_type: str,
    baseline_font_size: float,
) -> bool:
    """Join first line(s) on the next page with an unfinished paragraph/list_item (layout page break, not a new section)."""
    if line.page_number <= previous_line.page_number:
        return False
    if current_type not in {"paragraph", "list_item"}:
        return False
    if not _last_line_incomplete_for_page_flow(current_lines):
        return False
    incoming = _normalize_inline_text(line.text)
    if _looks_like_table_of_contents_header(incoming) or _looks_like_table_of_contents_entry(incoming):
        return False
    if line_type in {"metadata", "table_row"}:
        return False
    if current_type == "list_item" and line_type == "list_item" and _starts_new_list_item(line.text):
        return False
    if line_type == "heading":
        if _looks_like_legal_section_heading(line.text) and _is_header(line, baseline_font_size=baseline_font_size):
            return False
        return True
    return line_type in {"paragraph", "list_item"}


def _annotate_table_blocks(paragraphs: list[ExtractedParagraph]) -> list[ExtractedParagraph]:
    if not paragraphs:
        return paragraphs
    annotated: list[ExtractedParagraph] = []
    current_headers: list[str] | None = None
    previous_block_type: str | None = None
    for paragraph in paragraphs:
        if paragraph.block_type != "table_row":
            current_headers = None
            previous_block_type = paragraph.block_type
            annotated.append(paragraph)
            continue

        metadata = dict(paragraph.metadata or {})
        table_cells = [str(cell).strip() for cell in metadata.get("table_cells") or [] if str(cell).strip()]
        if previous_block_type != "table_row":
            current_headers = None

        if table_cells and current_headers is None and _looks_like_table_header_cells(tuple(table_cells)):
            metadata["table_role"] = "header"
            metadata["table_column_headers"] = list(table_cells)
            current_headers = table_cells
        else:
            metadata["table_role"] = "row" if table_cells else "unknown"
            if current_headers:
                metadata["table_column_headers"] = list(current_headers)

        annotated.append(replace(paragraph, metadata=metadata))
        previous_block_type = paragraph.block_type
    return annotated


def _annotate_special_blocks(paragraphs: list[ExtractedParagraph]) -> list[ExtractedParagraph]:
    annotated: list[ExtractedParagraph] = []
    for paragraph in paragraphs:
        metadata = dict(paragraph.metadata or {})
        if paragraph.block_type == "metadata":
            metadata["metadata_kind"] = "table_of_contents"
        annotated.append(replace(paragraph, metadata=metadata))
    return annotated


def extract_pdf_layout(raw: bytes) -> ExtractedDocument:
    import pdfplumber

    with pdfplumber.open(io.BytesIO(raw)) as pdf:
        page_count = len(pdf.pages)
        pdf_metadata = dict(pdf.metadata or {})
        page_lines: list[_PdfLine] = []
        for page_number, page in enumerate(pdf.pages, start=1):
            words = page.extract_words(
                use_text_flow=True,
                keep_blank_chars=False,
                split_at_punctuation=False,
                extra_attrs=["fontname", "size"],
            )
            page_lines.extend(_group_words_into_lines(words or [], page_number=page_number, page_height=float(page.height)))

    if not page_lines:
        return ExtractedDocument(
            text_content="",
            paragraphs=[],
            metadata={
                "source_format": "pdf",
                "extraction_engine": "pdfplumber_layout_v1",
                "page_count": page_count,
                "no_extractable_text": page_count > 0,
                "pdf_title": pdf_metadata.get("Title"),
                "pdf_producer": pdf_metadata.get("Producer"),
                "pdf_creator": pdf_metadata.get("Creator"),
            },
        )

    baseline_candidates = [line.font_size for line in page_lines if line.font_size > 0 and len(line.text) > 25]
    baseline_font_size = median(baseline_candidates or [line.font_size for line in page_lines if line.font_size > 0] or [11.0])
    repeated_edge_lines = _detect_repeated_edge_lines(page_lines)

    filtered_lines = [
        line
        for line in page_lines
        if (line.page_number, _normalize_repeat_key(line.text)) not in repeated_edge_lines and not _looks_like_edge_pagination(line)
    ]

    paragraphs: list[ExtractedParagraph] = []
    current_lines: list[_PdfLine] = []
    current_type = "paragraph"
    filtered_count = len(page_lines) - len(filtered_lines)

    def flush_current() -> None:
        nonlocal current_lines, current_type
        if not current_lines:
            return
        table_cells: tuple[str, ...] = ()
        if current_type == "table_row":
            merged_cells: list[str] = []
            for line in current_lines:
                merged_cells.extend(cell for cell in line.cell_texts if cell)
            table_cells = tuple(cell for cell in merged_cells if cell)
        text = (
            " | ".join(table_cells)
            if current_type == "table_row" and table_cells
            else _normalize_inline_text(" ".join(line.text for line in current_lines))
        )
        if not text:
            current_lines = []
            current_type = "paragraph"
            return
        bbox = (
            min(line.x0 for line in current_lines),
            min(line.top for line in current_lines),
            max(line.x1 for line in current_lines),
            max(line.bottom for line in current_lines),
        )
        page_number = current_lines[0].page_number
        font_size = median([line.font_size for line in current_lines if line.font_size > 0] or [baseline_font_size])
        is_bold = any(line.is_bold for line in current_lines)
        pages_spanned = sorted({ln.page_number for ln in current_lines})
        block_metadata: dict[str, Any] = {
            "line_count": len(current_lines),
            "page_number": page_number,
            "block_type": current_type,
            "table_cells": list(table_cells) if table_cells else [],
        }
        if len(pages_spanned) > 1:
            block_metadata["page_span"] = pages_spanned
        paragraphs.append(
            ExtractedParagraph(
                text=text,
                block_type=current_type,
                page_number=page_number,
                bbox=bbox,
                font_size=round(font_size, 2),
                is_bold=is_bold,
                metadata=block_metadata,
            )
        )
        current_lines = []
        current_type = "paragraph"

    previous_line: _PdfLine | None = None
    for line in filtered_lines:
        line_type = _line_block_type(line, baseline_font_size=baseline_font_size)
        if not current_lines:
            current_lines = [line]
            current_type = line_type
            previous_line = line
            continue

        assert previous_line is not None
        if _looks_like_empty_line_gap(previous_line, line) or _starts_forced_marker_break(line.text):
            flush_current()
            current_lines = [line]
            current_type = line_type
            previous_line = line
            continue

        current_lines.append(line)
        previous_line = line

    flush_current()

    paragraphs = _annotate_special_blocks(_annotate_table_blocks(paragraphs))
    text_content = "\n\n".join(paragraph.text for paragraph in paragraphs)
    block_counts = Counter(paragraph.block_type for paragraph in paragraphs)
    return ExtractedDocument(
        text_content=text_content,
        paragraphs=paragraphs,
        metadata={
            "source_format": "pdf",
            "extraction_engine": "pdfplumber_layout_v1",
            "page_count": page_count,
            "block_count": len(paragraphs),
            "filtered_edge_line_count": filtered_count,
            "block_counts": dict(block_counts),
            "baseline_font_size": round(float(baseline_font_size), 2),
            "pdf_title": pdf_metadata.get("Title"),
            "pdf_producer": pdf_metadata.get("Producer"),
            "pdf_creator": pdf_metadata.get("Creator"),
        },
    )


__all__ = ["extract_pdf_layout"]
