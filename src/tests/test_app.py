import pytest

import app
import config
from src.indexing.service import IndexingService
from src.tests.conftest import FakeIngestionPipeline, make_document


class FailingRAGService:
    def answer_with_context(self, question):
        raise RuntimeError("network down")


def test_question_loop_logs_error_and_continues(monkeypatch, caplog, capsys):
    questions = iter(["What?", "exit"])
    monkeypatch.setattr("builtins.input", lambda prompt: next(questions))

    app.run_question_loop(FailingRAGService())

    assert "Could not answer the question" in caplog.text
    assert "network down" in caplog.text
    assert capsys.readouterr().out.endswith("Ask a question, or type 'exit' to quit.\n")


def test_index_documents_saves_completed_work_before_failing(
    monkeypatch, tmp_path, embedding_service, repository
):
    documents_dir = tmp_path / "documents"
    documents_dir.mkdir()
    (documents_dir / "a.pdf").write_bytes(b"")
    (documents_dir / "b.pdf").write_bytes(b"")
    monkeypatch.setattr(config, "DOCUMENTS_DIR", documents_dir)

    calls = []

    def documents_for(path):
        calls.append(path)
        if len(calls) == 2:
            raise ValueError("broken pdf")
        return [make_document("cat")]

    with pytest.raises(ValueError, match="broken pdf"):
        app.index_documents(
            IndexingService(embedding_service, repository),
            FakeIngestionPipeline(documents_for),
        )

    assert repository.path.exists()


def test_main_logs_startup_failure_and_exits(monkeypatch, caplog):
    def fail():
        raise RuntimeError("bad config")

    monkeypatch.setattr(app, "build_container", fail)

    with pytest.raises(SystemExit) as exit_info:
        app.main()

    assert exit_info.value.code == 1
    assert "stopped because of an error" in caplog.text
    assert "bad config" in caplog.text
