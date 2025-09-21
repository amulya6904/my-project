"""Job management for processing tasks."""

import asyncio
import uuid
import os
import tempfile
from datetime import datetime
from typing import Dict, Optional, Any
from pathlib import Path
import logging

from .models import JobStatus, ProgressUpdate
from ..lib.api import BankStatementProcessor

logger = logging.getLogger(__name__)

# In-memory job storage (use Redis/database in production)
jobs: Dict[str, Dict[str, Any]] = {}
progress_callbacks: Dict[str, list] = {}


class JobManager:
    """Manages processing jobs and their lifecycle."""
    
    def __init__(self):
        self.processor = BankStatementProcessor()
        self.temp_dir = tempfile.mkdtemp(prefix="bank_processor_")
    
    def create_job(self, filename: str, file_size: int) -> str:
        """Create a new job entry."""
        job_id = str(uuid.uuid4())
        
        jobs[job_id] = {
            'id': job_id,
            'filename': filename,
            'size': file_size,
            'status': JobStatus.PENDING,
            'progress': 0,
            'message': 'Job created',
            'created_at': datetime.utcnow(),
            'completed_at': None,
            'error': None,
            'transactions': [],
            'csv_path': None,
            'bank_name': '',
            'processing_time': None
        }
        
        progress_callbacks[job_id] = []
        return job_id
    
    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job details."""
        return jobs.get(job_id)
    
    def update_progress(self, job_id: str, progress: int, message: str, 
                       status: Optional[JobStatus] = None):
        """Update job progress and notify callbacks."""
        if job_id not in jobs:
            return
            
        jobs[job_id]['progress'] = progress
        jobs[job_id]['message'] = message
        
        if status:
            jobs[job_id]['status'] = status
            
        # Notify WebSocket callbacks
        update = ProgressUpdate(
            job_id=job_id,
            progress=progress,
            message=message,
            status=jobs[job_id]['status']
        )
        
        for callback in progress_callbacks.get(job_id, []):
            try:
                asyncio.create_task(callback(update))
            except Exception as e:
                logger.error(f"Error in progress callback: {e}")
    
    async def process_job(self, job_id: str, pdf_path: str, password: Optional[str] = None):
        """Process a job asynchronously."""
        if job_id not in jobs:
            logger.error(f"Job {job_id} not found")
            return
            
        start_time = datetime.utcnow()
        
        try:
            self.update_progress(job_id, 10, "Starting PDF processing...", JobStatus.PROCESSING)
            
            # Process in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, 
                self._process_pdf_sync, 
                job_id, 
                pdf_path, 
                password
            )
            
            if result['status'] == 'success':
                self.update_progress(job_id, 90, "Exporting to CSV...", JobStatus.PROCESSING)
                
                csv_path = await loop.run_in_executor(
                    None,
                    self.processor.export_to_csv,
                    result['transactions']
                )
                
                # Update job with results
                end_time = datetime.utcnow()
                processing_time = (end_time - start_time).total_seconds()
                
                jobs[job_id].update({
                    'status': JobStatus.COMPLETED,
                    'progress': 100,
                    'message': f'Processing completed. Found {result["count"]} transactions.',
                    'completed_at': end_time,
                    'transactions': result['transactions'],
                    'csv_path': csv_path,
                    'bank_name': result['bank'],
                    'processing_time': processing_time
                })
                
                self.update_progress(job_id, 100, "Processing completed!", JobStatus.COMPLETED)
                
            else:
                jobs[job_id].update({
                    'status': JobStatus.FAILED,
                    'error': result.get('error', 'Processing failed'),
                    'completed_at': datetime.utcnow()
                })
                self.update_progress(job_id, 0, "Processing failed", JobStatus.FAILED)
                
        except Exception as e:
            logger.error(f"Job {job_id} processing error: {e}")
            jobs[job_id].update({
                'status': JobStatus.FAILED,
                'error': str(e),
                'completed_at': datetime.utcnow()
            })
            self.update_progress(job_id, 0, f"Error: {str(e)}", JobStatus.FAILED)
        
        finally:
            # Clean up temporary PDF file
            try:
                if os.path.exists(pdf_path):
                    os.unlink(pdf_path)
            except Exception as e:
                logger.warning(f"Failed to clean up {pdf_path}: {e}")
    
    def _process_pdf_sync(self, job_id: str, pdf_path: str, password: Optional[str]) -> Dict[str, Any]:
        """Synchronous PDF processing (runs in thread pool)."""
        try:
            self.update_progress(job_id, 30, "Reading PDF file...")
            
            result = self.processor.process_pdf(pdf_path, password)
            
            self.update_progress(job_id, 70, f"Extracted {result['count']} transactions...")
            
            return result
            
        except Exception as e:
            return {'status': 'error', 'error': str(e)}
    
    def add_progress_callback(self, job_id: str, callback):
        """Add a WebSocket callback for progress updates."""
        if job_id not in progress_callbacks:
            progress_callbacks[job_id] = []
        progress_callbacks[job_id].append(callback)
    
    def remove_progress_callback(self, job_id: str, callback):
        """Remove a WebSocket callback."""
        if job_id in progress_callbacks:
            try:
                progress_callbacks[job_id].remove(callback)
            except ValueError:
                pass
    
    def cleanup_job(self, job_id: str):
        """Clean up job data and files."""
        if job_id in jobs:
            job = jobs[job_id]
            
            # Clean up CSV file
            if job.get('csv_path') and os.path.exists(job['csv_path']):
                try:
                    os.unlink(job['csv_path'])
                except Exception as e:
                    logger.warning(f"Failed to clean up CSV {job['csv_path']}: {e}")
            
            # Remove job data
            del jobs[job_id]
            
        # Clean up callbacks
        if job_id in progress_callbacks:
            del progress_callbacks[job_id]


# Global job manager instance
job_manager = JobManager()