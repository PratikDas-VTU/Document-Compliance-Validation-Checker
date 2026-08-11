"""
docx_parser.py — Extracts structured text data from DOCX files using python-docx.
Returns the same doc_data dict shape as pdf_parser for uniform validator consumption.
"""
from __future__ import annotations
import threading
from typing import List, Dict, Any
from docx import Document
from docx.oxml.ns import qn


def parse_docx(filepath: str, cancel_event: threading.Event) -> Dict[str, Any]:
    """
    Parse a DOCX and return structured doc_data.

    doc_data keys:
        pages         : List[Dict] — simulated pages (paragraphs grouped by page-break)
        full_text     : str
        paragraphs    : List[str] — all non-empty paragraph texts
        page_count    : int (estimated)
        metadata      : Dict
    """
    doc = Document(filepath)

    paragraphs: List[str] = []
    pages: List[Dict[str, Any]] = []
    current_page_paras: List[str] = []
    page_num = 1

    images = []
    for para in doc.paragraphs:
        if cancel_event.is_set():
            raise RuntimeError("Cancelled")

        text = para.text.strip()

        # Detect explicit page breaks in XML
        has_page_break = False
        for run in para.runs:
            if run._element.xml and "w:lastRenderedPageBreak" in run._element.xml:
                has_page_break = True
                break
        # Also check for w:pageBreak in paragraph XML
        if not has_page_break:
            for br in para._element.iter(qn("w:br")):
                if br.get(qn("w:type")) == "page":
                    has_page_break = True
                    break

        if has_page_break and current_page_paras:
            pages.append({
                "page_num": page_num,
                "text": "\n".join(current_page_paras),
                "word_count": sum(len(p.split()) for p in current_page_paras),
                "blocks": current_page_paras[:],
            })
            page_num += 1
            current_page_paras = []

        if text:
            paragraphs.append(text)
            current_page_paras.append(text)

        # Extract drawings and images from this paragraph
        try:
            drawings = para._element.xpath('.//*[local-name()="drawing"] | .//*[local-name()="pict"]')
            for drawing in drawings:
                embeds = drawing.xpath('.//*[local-name()="blip"]/@*[local-name()="embed"]')
                ids = drawing.xpath('.//*[local-name()="imagedata"]/@*[local-name()="id"]')
                for rId in embeds + ids:
                    try:
                        if rId in doc.part.rels:
                            rel = doc.part.rels[rId]
                            if "image" in rel.target_ref.lower():
                                img_part = rel.target_part
                                images.append({
                                    "page_num": page_num,
                                    "image_bytes": img_part.blob,
                                    "image_ext": img_part.content_type.split('/')[-1] if img_part.content_type else "png",
                                    "width": 0,
                                    "height": 0
                                })
                    except Exception:
                        pass
        except Exception:
            pass

    # Flush last page
    if current_page_paras:
        pages.append({
            "page_num": page_num,
            "text": "\n".join(current_page_paras),
            "word_count": sum(len(p.split()) for p in current_page_paras),
            "blocks": current_page_paras[:],
        })

    # Fallback: if no page breaks found, treat as 1 page
    if not pages:
        all_text = "\n".join(paragraphs)
        pages = [{
            "page_num": 1,
            "text": all_text,
            "word_count": len(all_text.split()),
            "blocks": paragraphs[:],
        }]

    full_text = "\n".join(paragraphs)

    # Core properties
    metadata = {}
    try:
        cp = doc.core_properties
        metadata = {
            "author": cp.author or "",
            "title": cp.title or "",
            "created": str(cp.created) if cp.created else "",
            "modified": str(cp.modified) if cp.modified else "",
        }
    except Exception:
        pass

    return {
        "pages": pages,
        "full_text": full_text,
        "paragraphs": paragraphs,
        "page_count": len(pages),
        "metadata": metadata,
        "file_type": "docx",
        "images": images,
    }
