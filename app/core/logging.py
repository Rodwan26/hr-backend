import logging
import json
import uuid
from typing import Any, Dict
from pythonjsonlogger import jsonlogger
from contextvars import ContextVar

# Context variable to store request_id for the current task/request
request_id_var: ContextVar[str] = ContextVar("request_id", default="")

class CustomJsonFormatter(jsonlogger.JsonFormatter):
    def add_fields(self, log_record: Dict[str, Any], record: logging.LogRecord, message_dict: Dict[str, Any]) -> None:
        super(CustomJsonFormatter, self).add_fields(log_record, record, message_dict)
        
        # Inject correlation ID if available
        req_id = request_id_var.get()
        if req_id:
            log_record["request_id"] = req_id
        
        if not log_record.get("timestamp"):
            from datetime import datetime, timezone
            log_record["timestamp"] = datetime.now(timezone.utc).isoformat()
        
        if log_record.get("level"):
            log_record["level"] = log_record["level"].upper()
        else:
            log_record["level"] = record.levelname

def setup_logging():
    logger = logging.getLogger()
    log_handler = logging.StreamHandler()
    formatter = CustomJsonFormatter("%(timestamp) %(level) %(name) %(message)")
    log_handler.setFormatter(formatter)
    logger.addHandler(log_handler)
    logger.setLevel(logging.INFO)
    
    # Suppress verbose logs from some libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
