"""Simplified FastAPI application for bank statement processing."""

import os
import tempfile
from typing import Optional, List, Dict, Any
from pathlib import Path
import logging

from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# Import the working parsers from the CLI
from ..parsers.parser_factory import ParserFactory
from ..core.exceptions import (
    BankStatementProcessorError,
    UnsupportedBankError,
    PasswordProtectedPDFError,
    PDFProcessingError
)
# Import the analyzer entrypoint
from ..analyzer.cli import run_analysis as run_analyzer_analysis
from ..analyzer.analyzer import AnalysisReport
import json
import csv

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Bank Statement Processor API",
    description="Simple API for processing PDF bank statements and converting to CSV",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Maximum file size (50MB)
MAX_FILE_SIZE = 50 * 1024 * 1024


# Models for summary endpoint
class SummaryTransaction(BaseModel):
    date: Optional[str] = None
    debit: Optional[float] = 0
    credit: Optional[float] = 0
    category: Optional[str] = None

class SummaryRequest(BaseModel):
    transactions: List[SummaryTransaction]

class SummaryResponse(BaseModel):
    totalIncome: float
    totalExpenditure: float
    suggestions: str

@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "Bank Statement Processor API",
        "version": "1.0.0",
        "description": "Upload PDF bank statements and get transaction data",
        "supported_banks": ["Union Bank of India", "State Bank of India"],
        "endpoints": {
            "upload": "/api/upload",
            "health": "/health"
        }
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "message": "API is running"}


@app.post("/analyze/summary")
async def analyze_summary(request: SummaryRequest) -> SummaryResponse:
    """Compute totals and generate a brief suggestions paragraph (~100 words)."""
    try:
        total_income = 0.0
        total_expenditure = 0.0
        category_spend: Dict[str, float] = {}

        for t in request.transactions:
            debit = float(t.debit or 0)
            credit = float(t.credit or 0)
            cat = (t.category or "Others")
            total_expenditure += max(0.0, debit)
            total_income += max(0.0, credit)
            if debit > 0:
                category_spend[cat] = category_spend.get(cat, 0.0) + debit

        top = sorted(category_spend.items(), key=lambda x: x[1], reverse=True)[:3]
        top_str = ", ".join([f"{name} ({amount:.0f})" for name, amount in top]) if top else "no significant spend categories"

        savings = max(0.0, total_income - total_expenditure)
        suggestions = (
            f"Income and spending trends show key outflows in {top_str}. "
            f"Preserve a monthly surplus (approx {savings:.0f}) by tightening variable spends, "
            f"auditing subscriptions, and setting category caps. Automate savings, build an emergency fund, "
            f"and plan purchases to avoid impulse buys. Use reminders for bills and compare providers to lower costs."
        )

        return SummaryResponse(
            totalIncome=round(total_income, 2),
            totalExpenditure=round(total_expenditure, 2),
            suggestions=suggestions
        )
    except Exception as e:
        logger.error(f"Summary analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/upload")
async def upload_and_process_pdf(
    file: UploadFile = File(...),
    password: Optional[str] = None,
    analyze: bool = Query(True)
):
    """Upload and immediately process a PDF bank statement."""

    # Validate file
    if not file.filename or not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")

    # Check file size
    file_content = await file.read()
    if len(file_content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large")

    # Save file temporarily
    temp_path = None
    try:
        # Create temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
            temp_path = temp_file.name
            temp_file.write(file_content)

        logger.info(f"Processing PDF: {file.filename} (size: {len(file_content)} bytes)")

        # Use the existing parser factory
        try:
            parser = ParserFactory.create_parser(temp_path, password)
            bank_name = parser.__class__.__name__.replace('Parser', '')
            logger.info(f"Detected bank: {bank_name}")

            # Extract transactions using the working CLI code
            transactions = parser.extract_transactions()
            logger.info(f"Extracted {len(transactions)} transactions")

            # Convert transactions to serializable format
            transaction_list = _format_transactions(transactions)

            analysis_report = None
            if analyze:
                api_key = os.environ.get("GEMINI_API_KEY")
                if not api_key:
                    logger.warning("GEMINI_API_KEY not set. Skipping AI analysis.")
                else:
                    analysis_report = _run_ai_analysis(transaction_list, api_key)

            return {
                "success": True,
                "filename": file.filename,
                "bank": bank_name,
                "transactions": transaction_list,
                "analysis": analysis_report,
                "count": len(transaction_list),
                "message": f"Successfully processed {len(transaction_list)} transactions from {bank_name}"
            }

        except UnsupportedBankError as e:
            logger.error(f"Unsupported bank: {e}")
            return {
                "success": False,
                "error": "unsupported_bank",
                "message": "This bank is not supported yet",
                "details": str(e),
                "supported_banks": ["Union Bank of India", "State Bank of India"]
            }

        except PasswordProtectedPDFError as e:
            logger.error(f"Password required: {e}")
            return {
                "success": False,
                "error": "password_required",
                "message": "This PDF is password protected",
                "details": str(e)
            }

        except PDFProcessingError as e:
            logger.error(f"PDF processing failed: {e}")
            return {
                "success": False,
                "error": "processing_failed",
                "message": "Failed to process PDF",
                "details": str(e)
            }

        except Exception as e:
            logger.error(f"Unexpected error: {e}", exc_info=True)
            return {
                "success": False,
                "error": "internal_error",
                "message": "An unexpected error occurred",
                "details": str(e)
            }

    finally:
        # Clean up temporary file
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)

def _format_transactions(transactions: List[Any]) -> List[Dict[str, Any]]:
    """Convert transaction objects to a serializable list of dicts."""
    transaction_list = []
    for t in transactions:
        transaction_list.append({
            'date': t.date.isoformat() if t.date else None,
            'description': t.description,
            'reference': t.reference,
            'debit': float(t.debit) if t.debit else None,
            'credit': float(t.credit) if t.credit else None,
            'balance': float(t.balance) if t.balance else None,
            'transaction_type': t.transaction_type.value if hasattr(t.transaction_type, 'value') else str(t.transaction_type),
            'counterparty': t.counterparty,
            'bank_name': t.bank_name,
            'account_number': t.account_number
        })
    return transaction_list

def _run_ai_analysis(transactions: List[Dict[str, Any]], api_key: str) -> Optional[Dict[str, Any]]:
    """Run the AI analysis pipeline on a list of transactions."""
    
    # Create a temporary directory for analysis files
    with tempfile.TemporaryDirectory() as temp_dir:
        csv_path = Path(temp_dir) / "transactions.csv"
        output_dir = Path(temp_dir) / "analysis_output"
        
        # 1. Write transactions to a temporary CSV file
        try:
            with open(csv_path, 'w', newline='', encoding='utf-8') as f:
                if not transactions:
                    return None
                writer = csv.DictWriter(f, fieldnames=transactions[0].keys())
                writer.writeheader()
                writer.writerows(transactions)
        except (IOError, csv.Error) as e:
            logger.error(f"Failed to write temporary CSV for analysis: {e}")
            return None

        # 2. Run the analyzer
        try:
            logger.info("Starting AI analysis...")
            run_analyzer_analysis(
                csv_file=str(csv_path),
                output_dir=str(output_dir),
                provider='gemini',
                api_key=api_key,
                generate_charts=False # No need to save charts to disk for API
            )
            
            # 3. Read the JSON report
            report_path = output_dir / "analysis_report.json"
            if report_path.exists():
                with open(report_path, 'r', encoding='utf-8') as f:
                    analysis_report = json.load(f)
                logger.info("AI analysis completed successfully.")
                return analysis_report
            else:
                logger.error("Analysis ran but report JSON was not found.")
                return None

        except Exception as e:
            logger.error(f"An error occurred during AI analysis: {e}", exc_info=True)
            return None

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "internal_error",
            "message": "Internal server error",
            "details": str(exc)
        }
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.api.simple_main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info"
    )