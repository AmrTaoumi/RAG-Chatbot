from pathlib import Path

import pytest
from pdfminer.pdfparser import PDFSyntaxError

from fetcher import extract_pages

SAMPLE = Path(__file__).parent / "fixtures" / "sample.pdf"


def test_extract_pages_returns_numbered_pages():
    pages = extract_pages(SAMPLE.read_bytes())
    assert [p["page"] for p in pages] == [1, 2]
    assert pages[0]["text"] == "Page one text"
    assert pages[1]["text"] == "Page two text"


def test_extract_pages_rejects_non_pdf():
    with pytest.raises(PDFSyntaxError):
        extract_pages(b"not a pdf")
