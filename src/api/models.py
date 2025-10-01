"""Pydantic models for API requests and responses."""

from typing import Optional, List, Dict, Any
from enum import Enum
from datetime import datetime
from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    """Job processing status."""
    PENDING = "pending"
    PROCESSING = "processing" 
    COMPLETED = "completed"
    FAILED = "failed"


class UploadResponse(BaseModel):
    """Response for file upload."""
    job_id: str = Field(..., description="Unique job identifier")
    filename: str = Field(..., description="Original filename")
    size: int = Field(..., description="File size in bytes")
    status: JobStatus = Field(default=JobStatus.PENDING)
    error: Optional[str] = Field(None, description="Error message if processing failed")


class JobStatusResponse(BaseModel):
    """Response for job status check."""
    job_id: str
    status: JobStatus
    progress: int = Field(ge=0, le=100, description="Progress percentage")
    message: Optional[str] = None
    error: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None


class ProcessingResult(BaseModel):
    """Processing result data."""
    job_id: str
    status: JobStatus
    transactions_count: int
    bank_name: str
    csv_path: Optional[str] = None
    processing_time: Optional[float] = None


class TransactionData(BaseModel):
    """Individual transaction data."""
    date: str
    description: str
    reference: Optional[str] = None
    debit: Optional[float] = None
    credit: Optional[float] = None
    balance: float
    transaction_type: str
    counterparty: Optional[str] = None


class ProcessingResponse(BaseModel):
    """Complete processing response."""
    job_id: str
    status: JobStatus
    transactions: List[TransactionData] = []
    count: int = 0
    bank: str = ""
    csv_url: Optional[str] = None
    error: Optional[str] = None


class ProgressUpdate(BaseModel):
    """WebSocket progress update."""
    job_id: str
    progress: int = Field(ge=0, le=100)
    message: str
    status: JobStatus


class ErrorResponse(BaseModel):
    """Error response model."""
    error: str
    detail: Optional[str] = None
    job_id: Optional[str] = None