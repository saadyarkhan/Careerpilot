"""
src/parsing/jd_parser.py

Utility functions for extracting raw text from Job Descriptions.

Responsibilities:
- Read pasted Job Description text
- Read TXT files
- Read PDF files
- Read DOCX files
- Clean extracted text

This module DOES NOT:
- Call an LLM
- Analyze the Job Description
- Extract skills using AI
- Generate structured JSON

LLM-based Job Description analysis is handled by:
src/graph/nodes/jd_analyzer.py
"""

from pathlib import Path
from typing import Union

from docx import Document
from pypdf import PdfReader


class JDParser:
    """Utility class for extracting raw Job Description text."""

    @staticmethod
    def from_text(text: str) -> str:
        """
        Process a pasted Job Description.

        Args:
            text: Raw Job Description text.

        Returns:
            Cleaned Job Description text.
        """
        if not isinstance(text, str):
            raise TypeError("Job Description must be a string.")

        return JDParser.clean(text)

    @staticmethod
    def from_txt(file_path: Union[str, Path]) -> str:
        """
        Extract text from a TXT Job Description file.
        """
        with open(file_path, "r", encoding="utf-8") as file:
            text = file.read()

        return JDParser.clean(text)

    @staticmethod
    def from_pdf(file_path: Union[str, Path]) -> str:
        """
        Extract text from a PDF Job Description.
        """
        reader = PdfReader(str(file_path))
        pages = []

        for page in reader.pages:
            page_text = page.extract_text()

            if page_text:
                pages.append(page_text)

        return JDParser.clean("\n".join(pages))

    @staticmethod
    def from_docx(file_path: Union[str, Path]) -> str:
        """
        Extract text from a DOCX Job Description.
        """
        document = Document(str(file_path))
        paragraphs = []

        for paragraph in document.paragraphs:
            if paragraph.text.strip():
                paragraphs.append(paragraph.text)

        return JDParser.clean("\n".join(paragraphs))

    @staticmethod
    def extract(file_path: Union[str, Path]) -> str:
        """
        Automatically detect the Job Description file type and extract text.

        Supported formats:
        - TXT
        - PDF
        - DOCX
        """
        path = Path(file_path)
        suffix = path.suffix.lower()

        if suffix == ".txt":
            return JDParser.from_txt(path)

        if suffix == ".pdf":
            return JDParser.from_pdf(path)

        if suffix == ".docx":
            return JDParser.from_docx(path)

        raise ValueError(
            f"Unsupported Job Description format: {suffix}. "
            "Supported formats are TXT, PDF, and DOCX."
        )

    @staticmethod
    def clean(text: str) -> str:
        """
        Clean extracted Job Description text.

        - Removes empty lines
        - Removes extra whitespace
        - Normalizes line endings
        """
        lines = []

        for line in text.splitlines():
            cleaned_line = " ".join(line.split())

            if cleaned_line:
                lines.append(cleaned_line)

        return "\n".join(lines)
