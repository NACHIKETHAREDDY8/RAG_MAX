import json

import pytest
from pypdf import PdfWriter

from src.ingestion.errors import ParserError
from src.ingestion.parsers.csv_parser import CsvParser
from src.ingestion.parsers.docx_parser import DocxParser
from src.ingestion.parsers.html_parser import HtmlParser
from src.ingestion.parsers.json_parser import JsonParser
from src.ingestion.parsers.markdown_parser import MarkdownParser
from src.ingestion.parsers.pdf_parser import PdfParser
from src.ingestion.parsers.text_parser import TextParser
from src.tests.sample_files import write_docx, write_text_pdf


def text_of(parsed) -> str:
    assert len(parsed.sections) == 1
    return parsed.sections[0].text


# --- PDF -----------------------------------------------------------------


def test_pdf_returns_one_numbered_section_per_page(tmp_path):
    path = write_text_pdf(tmp_path / "a.pdf", ["First page", "Second page"])

    parsed = PdfParser().parse(path)

    assert [section.page_number for section in parsed.sections] == [1, 2]
    assert "First page" in parsed.sections[0].text
    assert "Second page" in parsed.sections[1].text
    assert parsed.metadata["page_count"] == 2


def test_pdf_keeps_blank_pages_so_page_numbers_stay_aligned(tmp_path):
    path = tmp_path / "blank.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.add_blank_page(width=72, height=72)
    with open(path, "wb") as file:
        writer.write(file)

    parsed = PdfParser().parse(path)

    assert [section.text for section in parsed.sections] == ["", ""]


def test_corrupt_pdf_raises_parser_error(tmp_path):
    path = tmp_path / "broken.pdf"
    path.write_bytes(b"%PDF-1.4\nthis is not a real pdf")

    with pytest.raises(ParserError, match="broken.pdf"):
        PdfParser().parse(path)


# --- DOCX ----------------------------------------------------------------


def test_docx_keeps_paragraphs_and_tables_in_order(tmp_path):
    parsed = DocxParser().parse(write_docx(tmp_path / "policy.docx"))

    assert text_of(parsed).splitlines() == [
        "Leave Policy",
        "Employees get 20 days of annual leave.",
        "Type | Days",
        "Sick | 10",
        "Unused leave carries over.",
    ]
    assert parsed.sections[0].page_number is None


def test_docx_reads_core_properties(tmp_path):
    parsed = DocxParser().parse(write_docx(tmp_path / "policy.docx"))

    assert parsed.metadata["author"] == "HR Team"
    assert parsed.metadata["title"] == "Leave Policy"
    assert len(parsed.metadata["date"]) == 10


# --- TXT -----------------------------------------------------------------


def test_txt_reads_utf8(tmp_path):
    path = tmp_path / "notes.txt"
    path.write_text("Café rules → none", encoding="utf-8")

    parsed = TextParser().parse(path)

    assert text_of(parsed) == "Café rules → none"
    assert parsed.metadata == {"encoding": "utf-8"}


def test_txt_falls_back_to_windows_encoding(tmp_path):
    path = tmp_path / "notes.txt"
    path.write_bytes("Café “quoted”".encode("cp1252"))

    parsed = TextParser().parse(path)

    assert text_of(parsed) == "Café “quoted”"
    assert parsed.metadata["encoding"] == "cp1252"


def test_txt_honours_byte_order_marks(tmp_path):
    utf8 = tmp_path / "bom8.txt"
    utf8.write_bytes("﻿hello".encode("utf-8"))
    utf16 = tmp_path / "bom16.txt"
    utf16.write_bytes("hello".encode("utf-16"))

    assert text_of(TextParser().parse(utf8)) == "hello"
    assert text_of(TextParser().parse(utf16)) == "hello"


# --- Markdown ------------------------------------------------------------


def test_markdown_is_rendered_to_plain_text(tmp_path):
    path = tmp_path / "guide.md"
    path.write_text(
        "# Leave Guide\n\n"
        "Annual leave is **20 days**. See [the portal](https://hr.example).\n\n"
        "- Sick leave\n- Parental leave\n\n"
        "```\nsubmit_request()\n```\n",
        encoding="utf-8",
    )

    parsed = MarkdownParser().parse(path)
    text = text_of(parsed)

    assert "Leave Guide" in text
    assert "Annual leave is 20 days. See the portal." in text
    assert "Sick leave\nParental leave" in text
    assert "submit_request()" in text
    for syntax in ("#", "**", "](", "```"):
        assert syntax not in text
    assert parsed.metadata["title"] == "Leave Guide"


def test_markdown_front_matter_becomes_metadata(tmp_path):
    path = tmp_path / "guide.md"
    path.write_text(
        "---\ntitle: \"Leave Guide\"\nauthor: HR Team\ndate: 2026-01-15T09:00\n"
        "tags: [hr]\n---\n# Heading\n\nBody text.\n",
        encoding="utf-8",
    )

    parsed = MarkdownParser().parse(path)

    assert parsed.metadata == {
        "title": "Leave Guide",
        "author": "HR Team",
        "date": "2026-01-15",
        "encoding": "utf-8",
    }
    assert "tags" not in text_of(parsed)
    assert text_of(parsed).startswith("Heading")


# --- HTML ----------------------------------------------------------------


def test_html_keeps_visible_text_only(tmp_path):
    path = tmp_path / "page.html"
    path.write_text(
        "<html><head><title>Leave</title>"
        "<meta name='author' content='HR Team'>"
        "<meta property='article:published_time' content='2026-01-15T10:00:00Z'>"
        "<style>p { color: red }</style></head>"
        "<body><script>track()</script>"
        "<h1>Leave Policy</h1><p>Annual leave is <b>20</b> days.</p>"
        "<ul><li>Sick</li><li>Parental</li></ul>"
        "<table><tr><th>Type</th><th>Days</th></tr><tr><td>Sick</td><td>10</td></tr></table>"
        "</body></html>",
        encoding="utf-8",
    )

    parsed = HtmlParser().parse(path)
    lines = [line for line in text_of(parsed).splitlines() if line]

    assert lines == [
        "Leave Policy",
        "Annual leave is 20 days.",
        "Sick",
        "Parental",
        "Type | Days",
        "Sick | 10",
    ]
    assert parsed.metadata["title"] == "Leave"
    assert parsed.metadata["author"] == "HR Team"
    assert parsed.metadata["date"] == "2026-01-15"


# --- CSV -----------------------------------------------------------------


def test_csv_rows_repeat_column_names(tmp_path):
    path = tmp_path / "leave.csv"
    path.write_text("type,days\nannual,20\nsick,10\n", encoding="utf-8")

    parsed = CsvParser().parse(path)

    assert text_of(parsed).splitlines() == [
        "Columns: type, days",
        "type: annual | days: 20",
        "type: sick | days: 10",
    ]
    assert parsed.metadata["row_count"] == 2
    assert parsed.metadata["column_count"] == 2


def test_csv_detects_semicolons_quotes_and_skips_blank_cells(tmp_path):
    path = tmp_path / "leave.csv"
    path.write_text('name;note;days\n"Doe; Jane";;20\n\n', encoding="utf-8")

    parsed = CsvParser().parse(path)

    assert text_of(parsed).splitlines()[1] == "name: Doe; Jane | days: 20"
    assert parsed.metadata["row_count"] == 1


def test_csv_names_extra_and_unnamed_columns(tmp_path):
    path = tmp_path / "leave.csv"
    path.write_text("type,\nannual,20,extra\n", encoding="utf-8")

    lines = text_of(CsvParser().parse(path)).splitlines()

    assert lines == [
        "Columns: type, column_2",
        "type: annual | column_2: 20 | column_3: extra",
    ]


# --- JSON ----------------------------------------------------------------


def test_json_flattens_to_key_paths(tmp_path):
    path = tmp_path / "policy.json"
    path.write_text(
        json.dumps(
            {
                "policy": "Leave",
                "rules": [{"type": "annual", "days": 20}, {"type": "sick", "paid": True}],
                "notes": None,
                "empty": {},
            }
        ),
        encoding="utf-8",
    )

    assert text_of(JsonParser().parse(path)).splitlines() == [
        "policy: Leave",
        "rules[0].type: annual",
        "rules[0].days: 20",
        "rules[1].type: sick",
        "rules[1].paid: true",
        "notes: null",
    ]


def test_json_top_level_array_and_scalar(tmp_path):
    array = tmp_path / "array.json"
    array.write_text('["a", "b"]', encoding="utf-8")
    scalar = tmp_path / "scalar.json"
    scalar.write_text('"just text"', encoding="utf-8")

    assert text_of(JsonParser().parse(array)) == "[0]: a\n[1]: b"
    assert text_of(JsonParser().parse(scalar)) == "just text"


def test_invalid_json_raises_parser_error(tmp_path):
    path = tmp_path / "broken.json"
    path.write_text("{not json", encoding="utf-8")

    with pytest.raises(ParserError, match="broken.json as json"):
        JsonParser().parse(path)
