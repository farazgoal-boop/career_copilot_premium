"""Convert USER_MANUAL.html to PDF using xhtml2pdf."""

from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) < 3:
        print("Usage: html_to_pdf.py <input.html> <output.pdf>")
        return 1
    html_path = Path(sys.argv[1])
    pdf_path = Path(sys.argv[2])
    if not html_path.is_file():
        print(f"HTML not found: {html_path}")
        return 1
    try:
        from xhtml2pdf import pisa
    except ImportError:
        print("xhtml2pdf not installed")
        return 1
    html = html_path.read_text(encoding="utf-8")
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    with pdf_path.open("wb") as handle:
        status = pisa.CreatePDF(html, dest=handle)
    if status.err:
        print("PDF conversion failed")
        return 1
    print(f"Wrote {pdf_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
