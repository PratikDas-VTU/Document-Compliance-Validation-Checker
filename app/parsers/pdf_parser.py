"""
pdf_parser.py — Extracts structured text data from PDF files using PyMuPDF.
Returns a doc_data dict consumed by all validators.
"""
from __future__ import annotations
import threading
from typing import List, Dict, Any
import fitz  # PyMuPDF


def parse_pdf(filepath: str, cancel_event: threading.Event) -> Dict[str, Any]:
    """
    Parse a PDF and return structured doc_data.

    doc_data keys:
        pages         : List[Dict] — {page_num, text, word_count, blocks}
        full_text     : str  — concatenated text of all pages
        paragraphs    : List[str] — all non-empty text blocks
        page_count    : int
        metadata      : Dict
    """
    doc = fitz.open(filepath)
    pages: List[Dict[str, Any]] = []
    paragraphs: List[str] = []
    full_text_parts: List[str] = []

    for page_index in range(len(doc)):
        if cancel_event.is_set():
            doc.close()
            raise RuntimeError("Cancelled")

        page = doc[page_index]
        text = page.get_text("text")  # plain text
        blocks = page.get_text("blocks")  # list of (x0,y0,x1,y1,text,block_no,block_type)

        words = [w for w in text.split() if w.strip()]
        word_count = len(words)

        # Collect paragraph-level blocks
        for block in blocks:
            if len(block) >= 5 and isinstance(block[4], str):
                block_text = block[4].strip()
                if block_text:
                    paragraphs.append(block_text)

        full_text_parts.append(text)
        # Extract images from page
        page_images = []
        try:
            for img_info in page.get_images(full=True):
                xref = img_info[0]
                try:
                    base_image = doc.extract_image(xref)
                    if base_image:
                        page_images.append({
                            "page_num": page_index + 1,
                            "image_bytes": base_image["image"],
                            "image_ext": base_image["ext"],
                            "width": base_image.get("width", 0),
                            "height": base_image.get("height", 0),
                        })
                except Exception:
                    pass
        except Exception:
            pass

        pages.append({
            "page_num": page_index + 1,
            "text": text,
            "word_count": word_count,
            "blocks": blocks,
            "images": page_images,
        })

    metadata = doc.metadata or {}
    
    # Collect all page images into a flat document images list
    all_images = []
    for p in pages:
        all_images.extend(p.get("images", []))
        
    doc.close()

    return {
        "pages": pages,
        "full_text": "\n".join(full_text_parts),
        "paragraphs": paragraphs,
        "page_count": len(pages),
        "metadata": metadata,
        "file_type": "pdf",
        "images": all_images,
    }
