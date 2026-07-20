"""
src/parsing/resume_parser.py

Utility functions for extracting raw text from resumes.

Responsibilities:
- Read PDF resumes
- Read DOCX resumes
- Clean extracted text
- Return plain text
"""
import docx
from pathlib import Path
from typing import Union
from docx import Document
from pypdf import PdfReader

class ResumeParser:
    """ Utility class for extracting resume text """


    @staticmethod
    def from_pdf(file_path: Union[str, Path]) -> str:
        """
        Extract text from a PDF resume.

        Args:
            file_path: Path to PDF file

        Returns:
            Extracted resume text
        """
        reader = PdfReader(str(file_path))
        pages = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                pages.append(text)
        return ResumeParser.clean("\n".join(pages))

    @staticmethod
    def from_docx(file_path: Union[str, Path]) -> str:
        """
        Extract text from a DOCX resume.

        Args:
            file_path: Path to DOCX file

        Returns:
            Extracted resume text
        """
        document= Document(str(file_path))
        paragraphs=[]
        for para in document.paragraphs:
            if para.text.strip():
                paragraphs.append(para.text)
        return ResumeParser.clean("\n".join(paragraphs))

    @staticmethod
    def extract_extension(file_path: Union[str, Path]) -> str:
        """
        Automatically detect resume type and extract text.

        Supported:
        - PDF
        - DOCX
        """
        path = Path(file_path)
        suffix = path.suffix.lower()

        if suffix == ".pdf":
            return ResumeParser.from_pdf(path)
        elif suffix == ".docx":
            return ResumeParser.from_docx(path)
        else:
            raise ValueError(f"Unsupported file type: {suffix}")


    @staticmethod
    def clean(text: str) -> str:
        """
        Basic text cleaning.

        - Remove empty lines
        - Remove extra whitespace
        - Normalize line endings
        """
        lines = []

        for line in text.splitlines():
            cleaned = " ".join(line.split())

            if cleaned:
                lines.append(cleaned)

        return "\n".join(lines)
    
    @staticmethod
    def extract(file_path: Union[str, Path]) -> str:
        """
        Automatically detect resume type and extract text.
        
        Args:
            file_path: Path to resume file
            
        Returns:
            Extracted resume text
        """
        file_path = Path(file_path)
        extension = file_path.suffix.lower()
        if extension == ".pdf":
            return ResumeParser.from_pdf(file_path)
        elif extension == ".docx":
            return ResumeParser.from_docx(file_path)
        else:
            raise ValueError(f"Unsupported file type: {extension}")

        