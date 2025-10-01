"""Tests for the upload endpoint ensuring correct status reporting."""

import sys
import types
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient


# Provide a lightweight stub for the BankStatementProcessor dependency used by JobManager.
lib_module = types.ModuleType("src.lib")
lib_module.__path__ = []  # Mark as package
api_module = types.ModuleType("src.lib.api")


class _StubBankStatementProcessor:
    def process_pdf(self, pdf_path: str, password: str | None = None):
        return {
            "status": "success",
            "transactions": [],
            "count": 0,
            "bank": "Stub Bank",
        }

    def export_to_csv(self, transactions):  # pragma: no cover - not exercised in these tests
        return "/tmp/stub.csv"


api_module.BankStatementProcessor = _StubBankStatementProcessor
setattr(lib_module, "api", api_module)
sys.modules.setdefault("src.lib", lib_module)
sys.modules.setdefault("src.lib.api", api_module)

from src.api.auth import verify_token
from src.api.jobs import job_manager, jobs, progress_callbacks
from src.api.main import app
from src.api.models import JobStatus
from src.parsers import parser_factory


@pytest.fixture(autouse=True)
def reset_job_store():
    """Ensure the in-memory job store is clean before and after each test."""
    jobs.clear()
    progress_callbacks.clear()
    yield
    jobs.clear()
    progress_callbacks.clear()


@pytest.fixture()
def client():
    """Return a FastAPI test client with authentication dependency overridden."""
    app.dependency_overrides[verify_token] = lambda: "test-user"
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(verify_token, None)


def test_upload_file_success_sets_completed_status(client, monkeypatch):
    """The endpoint should return COMPLETED only when parsing succeeds."""

    class DummyParser:
        bank_name = "Mock Bank"

        def extract_transactions(self):
            return [
                SimpleNamespace(
                    date="2024-01-01",
                    description="Deposit",
                    reference="REF123",
                    debit=None,
                    credit=150.0,
                    balance=150.0,
                    transaction_type="deposit",
                    counterparty="Employer",
                    bank_name="Mock Bank",
                    account_number="****1234",
                )
            ]

    def create_parser(_cls, _pdf_path, password=None):  # noqa: D401 - signature required for classmethod
        return DummyParser()

    monkeypatch.setattr(
        parser_factory.ParserFactory,
        "create_parser",
        classmethod(create_parser),
    )

    response = client.post(
        "/upload",
        files={"file": ("statement.pdf", b"pdf data", "application/pdf")},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == JobStatus.COMPLETED.value
    assert "error" not in data or data["error"] is None

    job = job_manager.get_job(data["job_id"])
    assert job is not None
    assert job["status"] == JobStatus.COMPLETED
    assert len(job["transactions"]) == 1


def test_upload_file_failure_returns_failed_status(client, monkeypatch):
    """If parsing fails, the endpoint should surface a FAILED status and error message."""

    def failing_parser(_cls, _pdf_path, password=None):  # noqa: D401 - signature required for classmethod
        raise RuntimeError("Unable to parse statement")

    monkeypatch.setattr(
        parser_factory.ParserFactory,
        "create_parser",
        classmethod(failing_parser),
    )

    response = client.post(
        "/upload",
        files={"file": ("broken.pdf", b"pdf data", "application/pdf")},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == JobStatus.FAILED.value
    assert "Unable to parse" in data["error"]

    job = job_manager.get_job(data["job_id"])
    assert job is not None
    assert job["status"] == JobStatus.FAILED
    assert job["error"] is not None
    assert "Unable to parse" in job["error"]

