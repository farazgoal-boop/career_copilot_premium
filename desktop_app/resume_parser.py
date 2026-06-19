"""Resume extraction and confirmation helpers for onboarding."""

from __future__ import annotations

from pathlib import Path
import re
from xml.etree import ElementTree
import zipfile

from .onboarding import ResumeConfirmation

SUPPORTED_RESUME_FORMATS = {".docx", ".pdf"}
WORD_NAMESPACE = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}


def extract_resume_text(resume_path: str | Path) -> ResumeConfirmation:
    path = Path(resume_path)
    extension = path.suffix.lower()

    if extension not in SUPPORTED_RESUME_FORMATS:
        raise ValueError("Resume upload supports PDF or DOCX files only.")

    if extension == ".docx":
        extracted_text = _extract_docx_text(path)
    else:
        extracted_text = _extract_pdf_text(path)

    return ResumeConfirmation(
        filename=path.name,
        extracted_text=extracted_text,
        confirmed=False,
        source_format=extension.lstrip("."),
    )


def confirm_resume_extraction(resume: ResumeConfirmation, confirmed: bool) -> ResumeConfirmation:
    return ResumeConfirmation(
        filename=resume.filename,
        extracted_text=resume.extracted_text,
        confirmed=confirmed,
        source_format=resume.source_format,
    )


def _extract_docx_text(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        document_xml = archive.read("word/document.xml")

    root = ElementTree.fromstring(document_xml)
    fragments = [node.text for node in root.findall(".//w:t", WORD_NAMESPACE) if node.text]
    extracted_text = _normalize_text(" ".join(fragments))
    if not extracted_text:
        raise ValueError("The DOCX resume did not contain extractable text.")
    return extracted_text


def _extract_pdf_text(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("PDF resume extraction requires the optional 'pypdf' package.") from exc

    reader = PdfReader(str(path))
    fragments = [page.extract_text() or "" for page in reader.pages]
    extracted_text = _normalize_text(" ".join(fragments))
    if not extracted_text:
        raise ValueError("The PDF resume did not contain extractable text.")
    return extracted_text


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()