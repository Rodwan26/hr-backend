import logging
import json
import traceback
from typing import Callable, Any, Dict
from datetime import datetime, timezone
from fastapi import BackgroundTasks
from sqlalchemy.orm import Session

from app.services.base import BaseService
from app.models.task import Task
from app.services.resume_ai import process_resume_analysis

logger = logging.getLogger(__name__)

# Registry of task handlers
TASK_HANDLERS = {
    "resume_analysis": process_resume_analysis
}

class TaskService(BaseService):
    """
    Manages persistent background tasks with DB state and retries.
    """

    def __init__(self, background_tasks: BackgroundTasks, db: Session):
        super().__init__(db)
        self.background_tasks = background_tasks

    def enqueue(self, task_type: str, payload: Dict[str, Any]):
        """
        Create a persistent task and schedule it for execution.
        """
        if task_type not in TASK_HANDLERS:
            raise ValueError(f"Unknown task type: {task_type}")

        # 1. Create DB Record (PENDING)
        task = Task(
            type=task_type,
            status="PENDING",
            payload=payload,
            organization_id=self.org_id
        )
        self.db.add(task)
        try:
            self.db.commit()
            self.db.refresh(task)
        except Exception:
            self.db.rollback()
            raise
        
        logger.info(f"Enqueued Task {task.id} [{task_type}]")

        # 2. Schedule Execution
        # We pass task_id to the generic processor
        self.background_tasks.add_task(self.process_task_wrapper, task.id)
        return task

    def process_task_wrapper(self, task_id: int):
        """
        Wrapper to handle DB session for the background thread.
        Since BackgroundTasks runs after response, we need a new session?
        Actually, FastAPI BackgroundTasks runs in the same thread pool but dependency injection session might be closed.
        We should create a new session here. 
        """
        # Create a new session for the background task
        from app.database import SessionLocal
        db = SessionLocal()
        try:
            self.process_task(db, task_id)
        except Exception as e:
            logger.error(f"Critical error in task wrapper for {task_id}: {e}")
        finally:
            db.close()

    def process_task(self, db: Session, task_id: int):
        """
        Core task execution logic with state management.
        """
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            logger.error(f"Task {task_id} not found during processing.")
            return

        # Double check status to avoid double processing if we had multiple workers
        if task.status not in ["PENDING", "RETRYING"]:
            return

        # Update to PROCESSING
        task.status = "PROCESSING"
        task.updated_at = datetime.now(timezone.utc)
        try:
            db.commit()
        except Exception:
            db.rollback()
            raise

        handler = TASK_HANDLERS.get(task.type)
        if not handler:
            task.error = f"No handler for type {task.type}"
            try:
                db.commit()
            except Exception:
                db.rollback()
                raise
            return

        try:
            logger.info(f"Processing Task {task.id} [{task.type}]")
            # Execute Handler
            result = handler(db, task.payload)
            
            # Success
            task.status = "COMPLETED"
            task.result = result
            task.updated_at = datetime.now(timezone.utc)
            try:
                db.commit()
            except Exception:
                db.rollback()
                raise
            logger.info(f"Task {task.id} Completed successfully.")

        except Exception as e:
            logger.error(f"Task {task.id} Failed: {str(e)}")
            logger.error(traceback.format_exc())
            
            task.error = str(e)
            task.retries += 1
            task.updated_at = datetime.now(timezone.utc)
            
            if task.retries < task.max_retries:
                task.status = "RETRYING"
                # In a real system, we'd schedule this. Here we might just leave it 
                # for a poller or re-enqueue if we want immediate retry strategy.
                # For simplicity, we mark it RETRYING.
            else:
                task.status = "FAILED"
            
            try:
                db.commit()
            except Exception:
                db.rollback()
                raise
