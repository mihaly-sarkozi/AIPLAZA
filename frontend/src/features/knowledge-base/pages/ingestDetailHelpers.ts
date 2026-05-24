import type { IngestRunTrace, IngestRunTraceClaim } from "../services";
import type { ParagraphRow } from "./ingestDetailTypes";

export function getBlockTypeLabel(value: unknown) {
  switch (value) {
    case "heading":
      return "Header / title";
    case "paragraph":
      return "Paragraph-like blokk";
    case "list_item":
      return "List item";
    case "table_row":
      return "Table-like blokk";
    case "metadata":
      return "Rövid meta sor";
    case "noise":
      return "Zajos blokk";
    default:
      return typeof value === "string" && value ? value : "Paragraph-like blokk";
  }
}

export function getSemanticBlockContextLabel(block: Record<string, unknown>) {
  const subject = String(block.primary_subject || "-");
  const spaceValues = Array.isArray(block.space_values) ? block.space_values : [];
  const timeValues = Array.isArray(block.time_values) ? block.time_values : [];
  const space = String(block.primary_space || spaceValues[0] || "-");
  const time = String(block.primary_time || timeValues[0] || "-");
  return `Alany: ${subject} | Hely: ${space} | Idő: ${time}`;
}

export function sourceLabelForBlock(block: Record<string, unknown>, trace: IngestRunTrace | null) {
  return trace?.source_name || String(block.source_name || block.source_title || block.source_id || "Forrás");
}

export function claimTextForBlockClaim(claim: IngestRunTraceClaim | undefined, fallbackId: unknown) {
  if (claim?.claim_text) return claim.claim_text;
  const subject = claim?.subject_text || "";
  const predicate = claim?.predicate || "";
  const objectText = claim?.object_text || "";
  const text = [subject, predicate, objectText].filter(Boolean).join(" ");
  return text || String(fallbackId || "Állítás");
}

export function getTableRoleLabel(value: unknown) {
  switch (value) {
    case "header":
      return "Táblafejléc";
    case "row":
      return "Adatsor";
    case "unknown":
      return "Ismeretlen táblasor";
    default:
      return typeof value === "string" && value ? value : "n/a";
  }
}

export function getMetadataKindLabel(value: unknown) {
  switch (value) {
    case "table_of_contents":
      return "Tartalomjegyzék";
    case "short_meta":
      return "Rövid meta sor";
    default:
      return typeof value === "string" && value ? value : "n/a";
  }
}

export function getNoiseKindLabel(value: unknown) {
  switch (value) {
    case "layout_noise":
      return "Layout zaj";
    default:
      return typeof value === "string" && value ? value : "n/a";
  }
}

export function getParagraphRoleSummary(paragraph: ParagraphRow) {
  const metadata = paragraph.metadata ?? {};
  const blockType = String(metadata.block_type ?? "");
  if (blockType === "table_row") {
    return getTableRoleLabel(metadata.table_role);
  }
  if (blockType === "metadata") {
    return getMetadataKindLabel(metadata.metadata_kind);
  }
  if (blockType === "noise") {
    return getNoiseKindLabel(metadata.noise_kind);
  }
  if (blockType === "heading") {
    return "Szakasz elválasztó";
  }
  if (blockType === "list_item") {
    return "Lista egység";
  }
  return "Normál blokk";
}

export function getParagraphDebugDetails(paragraph: ParagraphRow) {
  const metadata = paragraph.metadata ?? {};
  const details: string[] = [];
  if (typeof metadata.line_count === "number") {
    details.push(`${metadata.line_count} sor`);
  }
  const tableHeaders = Array.isArray(metadata.table_column_headers)
    ? metadata.table_column_headers.map((value) => String(value)).filter(Boolean)
    : [];
  const tableCells = Array.isArray(metadata.table_cells)
    ? metadata.table_cells.map((value) => String(value)).filter(Boolean)
    : [];
  if (tableHeaders.length) {
    details.push(`oszlopok: ${tableHeaders.join(" | ")}`);
  }
  if (tableCells.length) {
    details.push(`cellák: ${tableCells.join(" | ")}`);
  }
  if (typeof metadata.docx_table_row_index === "number") {
    details.push(`docx sor: ${metadata.docx_table_row_index + 1}`);
  }
  if (typeof metadata.docx_table_column_count === "number") {
    details.push(`oszlopszám: ${metadata.docx_table_column_count}`);
  }
  if (typeof metadata.font_size === "number") {
    details.push(`betűméret: ${metadata.font_size}`);
  }
  if (typeof metadata.is_bold === "boolean") {
    details.push(metadata.is_bold ? "félkövér" : "nem félkövér");
  }
  return details.length ? details.join(" | ") : "n/a";
}

export function getSplitReasonLabel(value: unknown) {
  switch (value) {
    case "strong_punctuation":
      return "Erős mondatzárás";
    case "medium_punctuation:semicolon":
      return "Pontosvessző";
    case "medium_punctuation:colon":
      return "Kettőspont";
    case "newline_candidate":
      return "Sortörés jelölt";
    case "long_segment_fallback":
      return "Hosszú szegmens fallback";
    case "heading_block":
      return "Heading blokk";
    case "list_item_block":
      return "Listaelem blokk";
    case "list_item_line":
      return "Lista sor";
    case "table_row_block":
      return "Táblasor blokk";
    case "structure_block":
      return "Szerkezeti blokk";
    case "tail":
      return "Maradék szegmens";
    case "fallback_single":
      return "Egyben hagyott blokk";
    default:
      return typeof value === "string" && value ? value : "n/a";
  }
}

export function formatSplitConfidence(value: unknown) {
  return typeof value === "number" ? `${Math.round(value * 100)}%` : "n/a";
}

export function formatStringList(value: unknown) {
  if (Array.isArray(value)) {
    const items = value.map((item) => String(item)).filter(Boolean);
    return items.length ? items.join(", ") : "n/a";
  }
  return typeof value === "string" && value ? value : "n/a";
}

export function getSplitStrengthLabel(value: unknown) {
  switch (value) {
    case "claim_refined":
      return "Claim-finomított";
    case "strong":
      return "Erős";
    case "weak":
      return "Gyenge";
    default:
      return typeof value === "string" && value ? value : "n/a";
  }
}

export function getSentenceSplitSummary(metadata: Record<string, unknown> | undefined) {
  const meta = metadata ?? {};
  const parts: string[] = [];
  if (meta.split_reason) {
    parts.push(getSplitReasonLabel(meta.split_reason));
  }
  if (meta.refined_from_reason) {
    parts.push(`alap: ${getSplitReasonLabel(meta.refined_from_reason)}`);
  }
  if (meta.split_strength) {
    parts.push(`erő: ${getSplitStrengthLabel(meta.split_strength)}`);
  }
  if (typeof meta.uncertain_split === "boolean") {
    parts.push(meta.uncertain_split ? "bizonytalan" : "stabil");
  }
  return parts.length ? parts.join(" | ") : "n/a";
}

export function getSentenceRefinementSummary(metadata: Record<string, unknown> | undefined) {
  const meta = metadata ?? {};
  const parts: string[] = [];
  if (meta.claim_split_reasons) {
    parts.push(`claim okok: ${formatStringList(meta.claim_split_reasons)}`);
  }
  if (meta.subject_hint) {
    parts.push(`S: ${String(meta.subject_hint)}`);
  }
  if (meta.predicate_hint) {
    parts.push(`P: ${String(meta.predicate_hint)}`);
  }
  if (meta.object_hint) {
    parts.push(`O: ${String(meta.object_hint)}`);
  }
  return parts.length ? parts.join(" | ") : "n/a";
}

export function getMentionTypeLabel(value: string) {
  const labels: Record<string, string> = {
    person: "Személy",
    organization: "Cég/szervezet",
    system: "Rendszer",
    place: "Hely",
    address: "Cím",
    email: "Email cím",
    phone_number: "Telefonszám",
    birth_date: "Születési dátum",
    tax_id: "Adószám",
    spanish_nif: "Spanyol NIF",
    spanish_nie: "Spanyol NIE",
    spanish_cif: "Spanyol CIF",
    eu_vat_number: "EU VAT / közösségi adószám",
    iban: "IBAN",
    bic_swift: "BIC / SWIFT",
    italian_codice_fiscale: "Olasz codice fiscale",
    french_siren: "Francia SIREN",
    french_siret: "Francia SIRET",
    polish_pesel: "Lengyel PESEL",
    romanian_cnp: "Román CNP",
    portuguese_nif: "Portugál NIF",
    license_plate: "Rendszám",
    vin: "Alvázszám",
    traffic_permit_number: "Forgalmi engedélyszám",
    driver_license_number: "Jogosítvány szám",
    social_security_number: "TB azonosító",
    company_registration_number: "Cégjegyzékszám",
    mixed_identifier: "Vegyes azonosító/kód",
    generic_identifier: "Általános azonosító",
    function: "Funkció",
    rule: "Szabály",
    role: "Szerepkör",
    document_reference: "Dokumentumhivatkozás",
    coreference: "Visszautalás",
  };
  return labels[value] ?? value;
}

export function getInformationValueStatusLabel(value: string) {
  const labels: Record<string, string> = {
    context_strong: "Erős kontextus",
    merge_with_previous: "Előzőhöz csatolandó",
    discard_candidate: "Eldobható jelölt",
    weak: "Gyenge",
    usable: "Használható",
    strong: "Erős",
    unrated: "Nincs értékelve",
  };
  return labels[value] ?? value;
}

export function getAssertionModeLabel(value: string) {
  const labels: Record<string, string> = {
    context_header: "Fejléc / kontextus",
  };
  return labels[value] ?? value;
}

export function getClaimTypeLabel(value: string) {
  const labels: Record<string, string> = {
    context_header: "Fejléc-kapcsolat",
  };
  return labels[value] ?? value;
}

export function getInformationValueBadgeClass(value: string) {
  switch (value) {
    case "strong":
      return "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300";
    case "usable":
      return "bg-blue-500/10 text-blue-700 dark:text-blue-300";
    case "weak":
      return "bg-amber-500/10 text-amber-700 dark:text-amber-300";
    case "merge_with_previous":
    case "discard_candidate":
      return "bg-rose-500/10 text-rose-700 dark:text-rose-300";
    default:
      return "bg-slate-500/10 text-slate-700 dark:text-slate-300";
  }
}
