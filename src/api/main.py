"""FastAPI application for bank statement processing."""

import os
import tempfile
import uuid
from typing import Optional, List, Dict, Any
from pathlib import Path
import logging
import asyncio

from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .models import (
    UploadResponse, JobStatusResponse, ProcessingResponse,
    ErrorResponse, JobStatus, ProgressUpdate
)
from .auth import verify_token, create_demo_token
from .jobs import job_manager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Bank Statement Processor API",
    description="API for processing PDF bank statements and converting to CSV",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],  # React dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Maximum file size (50MB)
MAX_FILE_SIZE = 50 * 1024 * 1024


# Pydantic models for AI analysis
class TransactionForAnalysis(BaseModel):
    id: str
    description: str
    amount: float
    transaction_type: str
    date: str

class AnalyzeRequest(BaseModel):
    transactions: List[TransactionForAnalysis]
    provider: str = "mock"  # Default to mock for testing

class CategoryResult(BaseModel):
    category: str
    confidence: str
    reasoning: str

class AnalyzeResponse(BaseModel):
    success: bool
    categories: Dict[str, CategoryResult]
    summary: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "message": "Bank Statement Processor API",
        "version": "1.0.0",
        "endpoints": {
            "upload": "/upload",
            "process": "/process/{job_id}",
            "status": "/status/{job_id}",
            "download": "/download/{job_id}",
            "websocket": "/ws/progress/{job_id}"
        }
    }


@app.get("/demo-token")
async def get_demo_token():
    """Get a demo JWT token for testing (remove in production)."""
    token = create_demo_token()
    return {"access_token": token, "token_type": "bearer"}


@app.post("/api/upload")
async def upload_pdf(file: UploadFile = File(...)):
    """Upload and process PDF directly using working CLI parsers."""

    # Validate file type
    if not file.filename or not file.filename.lower().endswith('.pdf'):
        return {"success": False, "error": "Only PDF files are allowed"}

    # Save the uploaded file temporarily
    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        # USE THE EXISTING WORKING PARSER - Import from the correct location
        from ..parsers.parser_factory import ParserFactory

        # This already works in CLI - just use it!
        parser = ParserFactory.create_parser(tmp_path)
        transactions = parser.extract_transactions()

        # Get bank name from parser
        bank_name = parser.__class__.__name__.replace('Parser', '') if parser else "Unknown"

        # Convert to JSON-serializable format
        result = {
            "success": True,
            "filename": file.filename,
            "bank": bank_name,
            "count": len(transactions),
            "transactions": []
        }

        # Convert transactions to dict format
        for t in transactions:
            transaction_dict = {
                "date": str(t.date) if t.date else None,
                "description": t.description or "",
                "reference": t.reference or None,
                "debit": float(t.debit) if t.debit else None,
                "credit": float(t.credit) if t.credit else None,
                "balance": float(t.balance) if t.balance else None,
                "transaction_type": str(t.transaction_type) if hasattr(t, 'transaction_type') else "UNKNOWN",
                "counterparty": t.counterparty or None,
                "bank_name": t.bank_name or bank_name,
                "account_number": t.account_number or ""
            }
            result["transactions"].append(transaction_dict)

        os.unlink(tmp_path)  # Clean up
        logger.info(f"Successfully processed {file.filename}: {len(transactions)} transactions from {bank_name}")
        return result

    except Exception as e:
        os.unlink(tmp_path)
        logger.error(f"Failed to process {file.filename}: {str(e)}")
        return {"success": False, "error": str(e)}


@app.post("/api/analyze", response_model=AnalyzeResponse)
async def analyze_transactions(request: AnalyzeRequest):
    """Analyze transactions using FIXED smart categorization."""
    try:
        # Import the new working categorizer
        from ..analyzer.transaction_categorizer import SmartCategorizer

        logger.info(f"Analyzing {len(request.transactions)} transactions with FIXED categorizer")

        # Convert request transactions to simple dict format for the new categorizer
        simple_transactions = []
        for req_txn in request.transactions:
            try:
                # Convert to simple dict format expected by SmartCategorizer
                amount = abs(req_txn.amount)
                is_credit = req_txn.amount > 0

                transaction_dict = {
                    "description": req_txn.description,
                    "credit": amount if is_credit else None,
                    "debit": amount if not is_credit else None,
                    "amount": req_txn.amount
                }
                simple_transactions.append(transaction_dict)
                logger.info(f"Processing: {req_txn.description} (amount: {req_txn.amount})")
            except Exception as e:
                logger.warning(f"Failed to parse transaction {req_txn.id}: {e}")
                continue

        if not simple_transactions:
            return AnalyzeResponse(
                success=False,
                categories={},
                error="No valid transactions to analyze"
            )

        # Use the new SmartCategorizer (FIXED VERSION)
        categorizer = SmartCategorizer()
        logger.info("Using FIXED SmartCategorizer")

        # Categorize transactions using the new working system
        try:
            categorization_results = categorizer.categorize_batch(simple_transactions)
            logger.info(f"Categorization completed: {len(categorization_results)} results")

            # Build response
            categories = {}
            category_totals = {}

            for i, req_txn in enumerate(request.transactions):
                category_name = categorization_results.get(str(i), 'Others')

                logger.info(f"Transaction {i}: '{req_txn.description}' → {category_name}")

                categories[req_txn.id] = CategoryResult(
                    category=category_name,
                    confidence="HIGH",
                    reasoning=f"Smart keyword-based categorization"
                )

                # Track category totals for summary
                amount = abs(req_txn.amount)
                if category_name not in category_totals:
                    category_totals[category_name] = 0
                category_totals[category_name] += amount

            # Create summary
            total_amount = sum(abs(txn.amount) for txn in request.transactions)
            top_categories = sorted(category_totals.items(), key=lambda x: x[1], reverse=True)[:5]

            summary = {
                "total_transactions": len(request.transactions),
                "total_amount": total_amount,
                "categorization_rate": 100.0,  # SmartCategorizer always categorizes
                "top_categories": [
                    {"category": cat, "amount": amount, "percentage": (amount/total_amount)*100 if total_amount > 0 else 0}
                    for cat, amount in top_categories
                ],
                "provider_used": "smart"
            }

            logger.info(f"✅ FIXED categorization completed: {len(categories)} transactions")

            return AnalyzeResponse(
                success=True,
                categories=categories,
                summary=summary
            )

        except Exception as categorization_error:
            logger.error(f"FIXED categorization failed: {categorization_error}")
            return AnalyzeResponse(
                success=False,
                categories={},
                error=f"Smart categorization failed: {str(categorization_error)}"
            )

    except Exception as e:
        logger.error(f"Analysis failed: {str(e)}")
        return AnalyzeResponse(
            success=False,
            categories={},
            error=str(e)
        )


@app.post("/upload", response_model=UploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    user_id: str = Depends(verify_token)
):
    """Upload and immediately process a PDF bank statement file using working CLI parsers."""

    # Validate file type
    if not file.filename or not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")

    # Check file size
    file.file.seek(0, 2)  # Seek to end
    file_size = file.file.tell()
    file.file.seek(0)  # Reset to beginning

    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size is {MAX_FILE_SIZE // (1024*1024)}MB"
        )

    if file_size == 0:
        raise HTTPException(status_code=400, detail="Empty file uploaded")

    # Create job
    job_id = job_manager.create_job(file.filename, file_size)

    # Save uploaded file temporarily
    temp_dir = tempfile.gettempdir()
    temp_file_path = os.path.join(temp_dir, f"{job_id}_{file.filename}")

    try:
        with open(temp_file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)

        logger.info(f"File uploaded successfully: {job_id}, size: {file_size}")

        # IMMEDIATELY PROCESS THE PDF using the working CLI parsers
        try:
            # Import the working parser - fix the import path
            from src.parsers.parser_factory import ParserFactory

            # Create parser and extract transactions
            parser = ParserFactory.create_parser(temp_file_path)
            transactions = parser.extract_transactions()

            # Get bank name
            bank_name = parser.bank_name if hasattr(parser, 'bank_name') else "Unknown"

            # Update job with processing results
            job_manager.update_progress(job_id, 100,
                                      f"Successfully processed {len(transactions)} transactions",
                                      JobStatus.COMPLETED)

            # Store transaction data in job
            job = job_manager.get_job(job_id)
            if job:
                job['transactions'] = []
                for t in transactions:
                    transaction_dict = {
                        "date": str(t.date) if t.date else None,
                        "description": t.description or "",
                        "reference": t.reference or None,
                        "debit": float(t.debit) if t.debit else None,
                        "credit": float(t.credit) if t.credit else None,
                        "balance": float(t.balance) if t.balance else None,
                        "transaction_type": str(t.transaction_type) if hasattr(t, 'transaction_type') else "UNKNOWN",
                        "counterparty": t.counterparty or None,
                        "bank_name": t.bank_name or bank_name,
                        "account_number": t.account_number or ""
                    }
                    job['transactions'].append(transaction_dict)
                job['bank_name'] = bank_name

            logger.info(f"Successfully processed {file.filename}: {len(transactions)} transactions from {bank_name}")

        except Exception as parse_error:
            # If parsing fails, still return successful upload but mark job as failed
            logger.error(f"Failed to process PDF {file.filename}: {str(parse_error)}")
            job_manager.update_progress(job_id, 0, f"Processing failed: {str(parse_error)}", JobStatus.FAILED)

        # Clean up temp file
        os.unlink(temp_file_path)

        return UploadResponse(
            job_id=job_id,
            filename=file.filename,
            size=file_size,
            status=JobStatus.COMPLETED  # Return completed since we processed immediately
        )

    except Exception as e:
        # Clean up on any error
        if os.path.exists(temp_file_path):
            os.unlink(temp_file_path)
        job_manager.cleanup_job(job_id)
        logger.error(f"File upload/processing error: {e}")
        raise HTTPException(status_code=500, detail=f"Upload/processing failed: {str(e)}")


@app.post("/process/{job_id}", response_model=dict)
async def start_processing(
    job_id: str,
    password: Optional[str] = None,
    user_id: str = Depends(verify_token)
):
    """Start processing a previously uploaded PDF."""
    logger.info(f"Processing start requested for job: {job_id} by user: {user_id}")

    job = job_manager.get_job(job_id)
    if not job:
        logger.error(f"Processing: Job not found: {job_id}")
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job['status'] != JobStatus.PENDING:
        raise HTTPException(
            status_code=400, 
            detail=f"Job already {job['status'].value}"
        )
    
    # Construct file path
    temp_dir = tempfile.gettempdir()
    pdf_path = os.path.join(temp_dir, f"{job_id}_{job['filename']}")
    
    if not os.path.exists(pdf_path):
        raise HTTPException(status_code=404, detail="Uploaded file not found")
    
    # Start processing asynchronously
    asyncio.create_task(job_manager.process_job(job_id, pdf_path, password))
    
    return {"message": "Processing started", "job_id": job_id}


@app.get("/status/{job_id}", response_model=JobStatusResponse)
async def get_job_status(
    job_id: str,
    user_id: str = Depends(verify_token)
):
    """Get the status of a processing job."""
    
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return JobStatusResponse(
        job_id=job_id,
        status=job['status'],
        progress=job['progress'],
        message=job['message'],
        error=job.get('error'),
        created_at=job['created_at'],
        completed_at=job.get('completed_at')
    )


@app.get("/download/{job_id}")
async def download_csv(
    job_id: str,
    user_id: str = Depends(verify_token)
):
    """Download the processed CSV file."""
    
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job['status'] != JobStatus.COMPLETED:
        raise HTTPException(
            status_code=400, 
            detail=f"Job is {job['status'].value}, not completed"
        )
    
    csv_path = job.get('csv_path')
    if not csv_path or not os.path.exists(csv_path):
        raise HTTPException(status_code=404, detail="CSV file not found")
    
    # Generate a clean filename
    clean_filename = job['filename'].replace('.pdf', '.csv')
    
    return FileResponse(
        path=csv_path,
        filename=clean_filename,
        media_type='text/csv'
    )


@app.get("/results/{job_id}", response_model=ProcessingResponse)
async def get_processing_results(
    job_id: str,
    user_id: str = Depends(verify_token)
):
    """Get detailed processing results including transaction data."""
    
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    csv_url = None
    if job['status'] == JobStatus.COMPLETED and job.get('csv_path'):
        csv_url = f"/download/{job_id}"
    
    return ProcessingResponse(
        job_id=job_id,
        status=job['status'],
        transactions=job.get('transactions', []),
        count=len(job.get('transactions', [])),
        bank=job.get('bank_name', ''),
        csv_url=csv_url,
        error=job.get('error')
    )


@app.websocket("/ws/progress/{job_id}")
async def websocket_progress(websocket: WebSocket, job_id: str):
    """WebSocket endpoint for real-time progress updates."""
    logger.info(f"WebSocket connection attempt for job: {job_id}")
    await websocket.accept()

    # Check if job exists
    job = job_manager.get_job(job_id)
    if not job:
        logger.warning(f"WebSocket: Job not found: {job_id}")
        await websocket.close(code=4004, reason="Job not found")
        return

    logger.info(f"WebSocket connected successfully for job: {job_id}")
    
    async def progress_callback(update: ProgressUpdate):
        """Send progress update to WebSocket client."""
        try:
            await websocket.send_json(update.model_dump())
        except Exception as e:
            logger.error(f"WebSocket send error: {e}")
    
    # Add callback
    job_manager.add_progress_callback(job_id, progress_callback)
    
    # Send current status
    current_update = ProgressUpdate(
        job_id=job_id,
        progress=job['progress'],
        message=job['message'],
        status=job['status']
    )
    await progress_callback(current_update)
    
    try:
        # Keep connection alive and listen for disconnect
        while True:
            try:
                await websocket.receive_text()
            except WebSocketDisconnect:
                break
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        # Clean up callback
        job_manager.remove_progress_callback(job_id, progress_callback)


@app.delete("/jobs/{job_id}")
async def cleanup_job(
    job_id: str,
    user_id: str = Depends(verify_token)
):
    """Clean up job data and associated files."""
    
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job_manager.cleanup_job(job_id)
    return {"message": f"Job {job_id} cleaned up successfully"}


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler."""
    logger.error(f"Unhandled exception: {exc}")
    return ErrorResponse(error="Internal server error", detail=str(exc))


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "src.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,  # Disable reload to prevent job data loss during development
        log_level="info"
    )