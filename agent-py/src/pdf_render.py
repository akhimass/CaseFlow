"""Markdown → PDF via weasyprint."""

from __future__ import annotations

import logging
import re

logger = logging.getLogger("pdf_render")

PDF_CSS = """
@page {
  size: letter;
  margin: 1in;
  @bottom-center {
    content: "Caseflowy · Page " counter(page);
    font-size: 9pt;
    color: #666;
  }
}
body {
  font-family: Georgia, Charter, "Times New Roman", serif;
  font-size: 11pt;
  line-height: 1.45;
  color: #111;
}
h1, h2, h3 { font-family: Georgia, Charter, serif; }
h1 { font-size: 18pt; margin-bottom: 0.5em; }
h2 { font-size: 14pt; margin-top: 1.2em; }
blockquote { border-left: 3px solid #ccc; padding-left: 1em; color: #444; }
code { font-size: 10pt; }
.cite-badge {
  font-size: 8pt;
  background: #eef2ff;
  color: #3730a3;
  padding: 1px 4px;
  border-radius: 3px;
}
"""


def markdown_to_html(markdown: str) -> str:
    try:
        import markdown as md_lib

        body = md_lib.markdown(markdown, extensions=["extra", "sane_lists"])
    except Exception:
        body = "<pre>" + _escape(markdown) + "</pre>"

    body = re.sub(
        r"\[cite:([^\]]+)\]",
        r'<span class="cite-badge">cite:\1</span>',
        body,
    )
    return f"<!DOCTYPE html><html><head><meta charset='utf-8'></head><body>{body}</body></html>"


def render_pdf_bytes(markdown: str) -> bytes | None:
    try:
        from weasyprint import HTML

        html = markdown_to_html(markdown)
        return HTML(string=html).write_pdf(stylesheets=[_css()])
    except Exception:
        logger.exception("PDF render failed")
        return None


def estimate_page_count(markdown: str) -> int:
    words = len(markdown.split())
    return max(1, round(words / 280))


def _css():
    from weasyprint import CSS

    return CSS(string=PDF_CSS)


def _escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
