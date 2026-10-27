import io

import pdfplumber

def extract_pages(pdf_bytes):
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        return [
            {"page": number, "text": page.extract_text() or ""}
            for number, page in enumerate(pdf.pages, start=1)
        ]
