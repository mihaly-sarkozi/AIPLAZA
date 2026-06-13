from __future__ import annotations

from io import BytesIO
from typing import Iterator

from docx.opc.constants import RELATIONSHIP_TYPE as RT

_SUPPORTED_IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg")


def iter_docx_embedded_images(document) -> Iterator[tuple[str, bytes]]:
    for rel in document.part.rels.values():
        if rel.reltype != RT.IMAGE:
            continue
        name = rel.target_ref.rsplit("/", 1)[-1]
        if not name.lower().endswith(_SUPPORTED_IMAGE_SUFFIXES):
            continue
        yield name, rel.target_part.blob


def open_image_blob(blob: bytes):
    from PIL import Image

    return Image.open(BytesIO(blob))


__all__ = ["iter_docx_embedded_images", "open_image_blob"]
