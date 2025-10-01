"""Tests for the asynchronous job manager and FastAPI bootstrap."""

from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path


from src.api.jobs import JobManager, JobStatus, jobs
from src.api.main import app
from src.parsers.base_parser import Transaction, TransactionType


def test_job_manager_process_flow(monkeypatch, tmp_path):
    """Ensure the job manager completes a mocked processing workflow."""

    transactions = [
        Transaction(
            date=datetime(2024, 1, 1),
            description="Salary",
            reference="PAY123",
            debit=None,
            credit=1000.0,
            balance=1000.0,
            transaction_type=TransactionType.DEPOSIT,
            counterparty="Acme Corp",
            bank_name="Test Bank",
            account_number="XXXX1234",
        )
    ]

    serialized_transactions = [
        {
            'date': transactions[0].date.isoformat(),
            'description': transactions[0].description,
            'reference': transactions[0].reference,
            'debit': transactions[0].debit,
            'credit': transactions[0].credit,
            'balance': transactions[0].balance,
            'transaction_type': transactions[0].transaction_type.value,
            'counterparty': transactions[0].counterparty,
            'bank_name': transactions[0].bank_name,
            'account_number': transactions[0].account_number,
        }
    ]

    class DummyProcessor:
        def __init__(self, output_dir: str | None = None) -> None:
            self.output_dir = Path(output_dir) if output_dir else tmp_path
            self.output_dir.mkdir(parents=True, exist_ok=True)

        def process_pdf(self, pdf_path: str, password=None):
            return {
                'status': 'success',
                'transactions': transactions,
                'transactions_data': serialized_transactions,
                'count': len(transactions),
                'bank': 'Test Bank',
                'account_number': 'XXXX1234',
            }

        def export_to_csv(self, txns, bank_name, account_number=None):
            output_path = self.output_dir / 'output.csv'
            output_path.write_text('id,amount\n1,1000\n', encoding='utf-8')
            return str(output_path)

    monkeypatch.setattr('src.api.jobs.BankStatementProcessor', DummyProcessor)

    manager = JobManager()
    job_id = manager.create_job('statement.pdf', 123)

    pdf_path = tmp_path / 'statement.pdf'
    pdf_path.write_text('dummy pdf content', encoding='utf-8')

    asyncio.run(manager.process_job(job_id, str(pdf_path)))

    job_data = manager.get_job(job_id)
    assert job_data is not None
    assert job_data['status'] == JobStatus.COMPLETED
    assert job_data['bank_name'] == 'Test Bank'
    assert job_data['transactions'] == serialized_transactions
    assert Path(job_data['csv_path']).exists()

    manager.cleanup_job(job_id)
    assert job_id not in jobs


def test_fastapi_app_startup():
    """Verify the FastAPI application boots and exposes the root endpoint."""

    routes = {route.path for route in app.router.routes}

    assert "/" in routes
    assert any(getattr(route, "name", "") == "root" for route in app.router.routes)
