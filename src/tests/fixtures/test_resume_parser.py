"""
Tests for src/parsing/resume_parser.py
"""

from pathlib import Path

import pytest

from parsing.resume_parser import ResumeParser


def test_clean_text_removes_extra_spaces_and_empty_lines():
    raw_text = """
    
    Saad     Khan
    
    
    Python     SQL
    
    """

    result = ResumeParser.clean(raw_text)

    expected = "Saad Khan\nPython SQL"

    assert result == expected


def test_extract_raises_error_for_unsupported_file():
    with pytest.raises(ValueError, match="Unsupported resume format"):
        ResumeParser.extract("resume.txt")


def test_extract_calls_pdf_parser(monkeypatch):
    expected_text = "Resume PDF Content"

    monkeypatch.setattr(
        ResumeParser,
        "from_pdf",
        lambda file_path: expected_text
    )

    result = ResumeParser.extract("resume.pdf")

    assert result == expected_text


def test_extract_calls_docx_parser(monkeypatch):
    expected_text = "Resume DOCX Content"

    monkeypatch.setattr(
        ResumeParser,
        "from_docx",
        lambda file_path: expected_text
    )

    result = ResumeParser.extract("resume.docx")

    assert result == expected_text