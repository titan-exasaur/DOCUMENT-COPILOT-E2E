from pathlib import Path
from pypdf import PdfReader
from typing import List, Dict

def document_loader(pdf_path: Path) -> List[Dict[str, str]]:
    """
    Loads a PDF and extracts text page by page.

    Returns:
        List of dictionaries with page number and text
    """

    if pdf_path is None:
        raise ValueError("No file provided")

    reader = PdfReader(pdf_path)
    documents = []

    for page_number, page in enumerate(reader.pages):
        text = page.extract_text()

        if text:
            documents.append({
                "page": str(page_number + 1),
                "text": text
            })

    return documents