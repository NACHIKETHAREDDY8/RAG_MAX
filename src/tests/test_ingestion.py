import hashlib
import json

import pytest

import app
import config
from src.indexing.service import IndexingService
from src.ingestion.detection import FileType, detect_file_type
from src.ingestion.errors import (
    FileValidationError,
    IngestionError,
    ParserError,
    UnsupportedFileTypeError,
)
from src.ingestion.models import ParsedDocument, ParsedSection
from src.ingestion.parsers.base import BaseParser
from src.ingestion.parsers.factory import ParserFactory, default_parser_factory
from src.ingestion.pipeline import IngestionPipeline, find_documents
from src.ingestion.validation import validate_file
from src.retrieval.service import RetrievalService
from src.tests.sample_files import write_sample, write_text_pdf

ALL_EXTENSIONS = [".pdf", ".docx", ".txt", ".md", ".html", ".csv", ".json"]


# --- validation ------------------------------------------------------------


def test_validate_file_accepts_normal_file(tmp_path):
    path = tmp_path / "a.txt"
    path.write_text("hello", encoding="utf-8")

    assert validate_file(str(path), max_size_bytes=100) == path


@pytest.mark.parametrize(
    ("setup", "message"),
    [
        (lambda path: None, "File not found"),
        (lambda path: path.mkdir(), "Not a file"),
        (lambda path: path.write_bytes(b""), "is empty"),
        (lambda path: path.write_bytes(b"x" * 101), "the limit is"),
    ],
)
def test_validate_file_rejects_bad_input(tmp_path, setup, message):
    path = tmp_path / "a.txt"
    setup(path)

    with pytest.raises(FileValidationError, match=message):
        validate_file(path, max_size_bytes=100)


# --- type detection ----------------------------------------------------------


@pytest.mark.parametrize(
    ("extension", "file_type", "mime_type"),
    [
        (".pdf", FileType.PDF, "application/pdf"),
        (".docx", FileType.DOCX, "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
        (".txt", FileType.TXT, "text/plain"),
        (".md", FileType.MARKDOWN, "text/markdown"),
        (".html", FileType.HTML, "text/html"),
        (".csv", FileType.CSV, "text/csv"),
        (".json", FileType.JSON, "application/json"),
    ],
)
def test_detects_every_supported_format(tmp_path, extension, file_type, mime_type):
    detected = detect_file_type(write_sample(tmp_path, extension))

    assert detected.file_type is file_type
    assert detected.mime_type == mime_type


def test_extension_matching_ignores_case_and_accepts_aliases(tmp_path):
    for name, file_type in [("A.TXT", FileType.TXT), ("b.htm", FileType.HTML), ("c.markdown", FileType.MARKDOWN)]:
        path = tmp_path / name
        path.write_text("text", encoding="utf-8")
        assert detect_file_type(path).file_type is file_type


def test_mime_type_is_used_when_the_extension_is_unknown(tmp_path):
    path = tmp_path / "upload.bin"
    path.write_text("a,b\n1,2\n", encoding="utf-8")

    assert detect_file_type(path, mime_type="text/csv; charset=utf-8").file_type is FileType.CSV


def test_unknown_type_is_unsupported(tmp_path):
    path = tmp_path / "slides.pptx"
    path.write_bytes(b"data")

    with pytest.raises(UnsupportedFileTypeError, match="'.pptx'.*Supported extensions"):
        detect_file_type(path)


@pytest.mark.parametrize(
    ("name", "content"),
    [
        ("fake.pdf", b"<html>not a pdf</html>"),
        ("fake.docx", b"plain text, not a zip"),
        ("binary.txt", b"\x89PNG\r\n\x1a\n\x00\x00\x00"),
    ],
)
def test_content_must_match_the_extension(tmp_path, name, content):
    path = tmp_path / name
    path.write_bytes(content)

    with pytest.raises(FileValidationError):
        detect_file_type(path)


def test_zip_without_word_document_is_not_docx(tmp_path):
    import zipfile

    path = tmp_path / "archive.docx"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("readme.txt", "hi")

    with pytest.raises(FileValidationError, match="not a valid DOCX"):
        detect_file_type(path)


# --- parser selection --------------------------------------------------------


def test_default_factory_has_a_parser_for_every_type():
    factory = default_parser_factory()

    assert factory.supported_types == set(FileType)
    for file_type in FileType:
        assert factory.get_parser(file_type).file_type is file_type


def test_factory_without_a_parser_reports_unsupported():
    with pytest.raises(UnsupportedFileTypeError, match="csv"):
        ParserFactory().get_parser(FileType.CSV)


def test_registered_parser_replaces_the_default(tmp_path):
    class UpperTextParser(BaseParser):
        file_type = FileType.TXT

        def _parse(self, path):
            return ParsedDocument([ParsedSection(path.read_text().upper())])

    factory = default_parser_factory()
    factory.register(UpperTextParser())
    path = tmp_path / "a.txt"
    path.write_text("hello", encoding="utf-8")

    assert IngestionPipeline(factory).ingest(path).documents[0].text == "HELLO"


def test_unexpected_parser_failure_becomes_parser_error(tmp_path):
    class ExplodingParser(BaseParser):
        file_type = FileType.TXT

        def _parse(self, path):
            raise KeyError("boom")

    path = tmp_path / "a.txt"
    path.write_text("hello", encoding="utf-8")

    with pytest.raises(ParserError, match="a.txt as txt.*boom") as error:
        IngestionPipeline(ParserFactory([ExplodingParser()])).ingest(path)

    assert isinstance(error.value.__cause__, KeyError)


# --- pipeline ----------------------------------------------------------------


@pytest.mark.parametrize("extension", ALL_EXTENSIONS)
def test_every_format_becomes_cleaned_documents(tmp_path, extension):
    path = write_sample(tmp_path, extension)

    result = IngestionPipeline().ingest(path)

    assert len(result.documents) == 1
    document = result.documents[0]
    assert "20" in document.text and "leave" in document.text.lower()
    assert document.filename == path.name
    assert document.source == str(path)
    assert document.metadata["source_type"] == result.file_type.value
    assert document.metadata["file_hash"] == result.file_hash
    assert document.page_number == (1 if extension == ".pdf" else None)


def test_document_ids_are_sha256_prefix_and_section(tmp_path):
    path = write_text_pdf(tmp_path / "a.pdf", ["One", "Two"])
    file_hash = hashlib.sha256(path.read_bytes()).hexdigest()

    result = IngestionPipeline().ingest(path)

    assert result.file_hash == file_hash
    assert [document.document_id for document in result.documents] == [
        f"{file_hash[:16]}-1",
        f"{file_hash[:16]}-2",
    ]


def test_identical_content_under_another_name_gets_the_same_ids(tmp_path):
    first = tmp_path / "a.txt"
    second = tmp_path / "copy.txt"
    first.write_text("same words", encoding="utf-8")
    second.write_text("same words", encoding="utf-8")
    pipeline = IngestionPipeline()

    assert (
        pipeline.ingest(first).documents[0].document_id
        == pipeline.ingest(second).documents[0].document_id
    )


def test_empty_sections_are_skipped_but_keep_their_number(tmp_path):
    path = write_text_pdf(tmp_path / "a.pdf", ["One", " ", "Three"])

    documents = IngestionPipeline().ingest(path).documents

    assert [document.page_number for document in documents] == [1, 3]
    assert documents[1].document_id.endswith("-3")


def test_file_without_text_gives_no_documents(tmp_path):
    path = tmp_path / "empty.json"
    path.write_text("{}", encoding="utf-8")

    result = IngestionPipeline().ingest(path)

    assert result.documents == []
    assert result.metadata["source_type"] == "json"


def test_metadata_combines_file_format_and_sidecar(tmp_path):
    path = tmp_path / "guide.md"
    path.write_text("---\nauthor: someone\n---\n# Guide\n\ntext", encoding="utf-8")
    (tmp_path / "guide.meta.json").write_text(
        json.dumps({"author": "HR Team", "department": "HR", "title": "Leave Guide"}),
        encoding="utf-8",
    )

    metadata = IngestionPipeline().ingest(path).metadata

    assert metadata == {
        "file_size": path.stat().st_size,
        "source_type": "markdown",
        "mime_type": "text/markdown",
        "file_hash": hashlib.sha256(path.read_bytes()).hexdigest(),
        "encoding": "utf-8",
        "author": "HR Team",
        "department": "HR",
        "title": "Leave Guide",
    }


def test_sidecar_with_invalid_json_is_an_ingestion_error(tmp_path):
    path = tmp_path / "a.txt"
    path.write_text("text", encoding="utf-8")
    (tmp_path / "a.meta.json").write_text("{oops", encoding="utf-8")

    with pytest.raises(IngestionError, match="a.meta.json is not valid JSON"):
        IngestionPipeline().ingest(path)


def test_pipeline_rejects_files_over_the_size_limit(tmp_path):
    path = tmp_path / "big.txt"
    path.write_text("x" * 2000, encoding="utf-8")

    with pytest.raises(FileValidationError, match="limit"):
        IngestionPipeline(max_file_size_bytes=1000).ingest(path)


def test_find_documents_skips_sidecars_hidden_files_and_folders(tmp_path):
    for name in ["b.pdf", "a.txt", "a.meta.json", "data.json", ".hidden.txt", "notes.xyz"]:
        (tmp_path / name).write_text("x", encoding="utf-8")
    (tmp_path / "folder").mkdir()

    names = [path.name for path in find_documents(tmp_path)]

    assert names == ["a.txt", "b.pdf", "data.json", "notes.xyz"]


# --- the app with the real pipeline -----------------------------------------------


@pytest.fixture
def documents_dir(monkeypatch, tmp_path):
    directory = tmp_path / "documents"
    directory.mkdir()
    monkeypatch.setattr(config, "DOCUMENTS_DIR", directory)
    return directory


def test_index_documents_skips_bad_files_and_indexes_the_rest(
    documents_dir, capsys, embedding_service, repository
):
    (documents_dir / "slides.pptx").write_bytes(b"data")
    (documents_dir / "fake.pdf").write_text("not a pdf", encoding="utf-8")
    (documents_dir / "broken.json").write_text("{oops", encoding="utf-8")
    (documents_dir / "empty.txt").write_bytes(b"")
    (documents_dir / "notes.txt").write_text("the cat sat", encoding="utf-8")

    app.index_documents(IndexingService(embedding_service, repository), IngestionPipeline())

    output = capsys.readouterr().out
    assert "Skipped slides.pptx: Unsupported file type '.pptx'" in output
    assert "Skipped fake.pdf: fake.pdf is not a valid PDF file." in output
    assert "Skipped broken.json: Could not read broken.json as json" in output
    assert "Skipped empty.txt: empty.txt is empty." in output
    assert "Extracted 1 section" in output
    assert [record.metadata["filename"] for record in repository.vector_store.list_records()] == [
        "notes.txt"
    ]
    assert repository.path.exists()


def test_index_documents_reports_duplicates_and_files_without_text(
    documents_dir, capsys, embedding_service, repository
):
    (documents_dir / "a.txt").write_text("the cat sat", encoding="utf-8")
    (documents_dir / "b.txt").write_text("the cat sat", encoding="utf-8")
    (documents_dir / "blank.json").write_text("[]", encoding="utf-8")

    app.index_documents(IndexingService(embedding_service, repository), IngestionPipeline())

    output = capsys.readouterr().out
    assert "Duplicate of a.txt, skipping b.txt" in output
    assert "No text found in blank.json, skipping" in output
    assert repository.count() == 1


def test_every_format_is_indexed_and_filterable(
    documents_dir, embedding_service, repository, tmp_path
):
    for extension in ALL_EXTENSIONS:
        write_sample(documents_dir, extension)
    (documents_dir / "sample.meta.json").write_text(
        json.dumps({"department": "HR", "tenant_id": "company_A"}), encoding="utf-8"
    )

    app.index_documents(IndexingService(embedding_service, repository), IngestionPipeline())

    records = repository.vector_store.list_records()
    assert {record.metadata["source_type"] for record in records} == {
        file_type.value for file_type in FileType
    }
    assert {record.metadata["department"] for record in records} == {"HR"}

    retrieval = RetrievalService(embedding_service, repository)
    results = retrieval.retrieve(
        "leave", top_k=10, filters={"tenant_id": "company_A", "source_type": "csv"}
    )
    assert [result.filename for result in results] == ["sample.csv"]
    assert results[0].page is None

    pdf = retrieval.retrieve("leave", filters={"source_type": "pdf"})[0]
    assert (pdf.filename, pdf.page) == ("sample.pdf", 1)
