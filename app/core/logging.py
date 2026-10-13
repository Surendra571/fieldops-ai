import json
import logging
import re
import sys
from contextvars import ContextVar
from datetime import UTC, datetime

# Global context variable for propagating request/correlation IDs across async calls
request_id_ctx: ContextVar[str] = ContextVar("request_id", default="")


class PIIRedactionFilter(logging.Filter):
    """
    Scrubs sensitive customer PII and authentication secrets from log records.
    Redacts phone numbers, email addresses, bearer tokens, passwords/api_keys,
    credit card numbers, and SSNs.
    """

    PHONE_REGEX = re.compile(r"(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}")
    EMAIL_REGEX = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
    BEARER_TOKEN_REGEX = re.compile(r"Bearer\s+\S+", re.IGNORECASE)
    SECRET_REGEX = re.compile(
        r'((?:api[-_]?key|secret|password|token)["\']?\s*[:=]\s*["\']?)(?:[^"\'\s,]+)(["\']?)',
        re.IGNORECASE,
    )
    SSN_REGEX = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
    CREDIT_CARD_REGEX = re.compile(
        r"\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}|3(?:0[0-5]|[68][0-9])[0-9]{11}|6(?:011|5[0-9]{2})[0-9]{12})\b"
    )

    @classmethod
    def redact(cls, text: str) -> str:
        if not isinstance(text, str):
            return text
        text = cls.SSN_REGEX.sub("[REDACTED_SSN]", text)
        text = cls.CREDIT_CARD_REGEX.sub("[REDACTED_CREDIT_CARD]", text)
        text = cls.PHONE_REGEX.sub("[REDACTED_PHONE]", text)
        text = cls.EMAIL_REGEX.sub("[REDACTED_EMAIL]", text)
        text = cls.BEARER_TOKEN_REGEX.sub("Bearer [REDACTED_TOKEN]", text)
        text = cls.SECRET_REGEX.sub(r"\1[REDACTED_SECRET]\2", text)
        return text

    def filter(self, record: logging.LogRecord) -> bool:
        # Attach request_id to record if not already present
        if not hasattr(record, "request_id"):
            record.request_id = request_id_ctx.get() or "-"

        if isinstance(record.msg, str):
            record.msg = self.redact(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {k: self.redact(str(v)) for k, v in record.args.items()}
            elif isinstance(record.args, tuple):
                record.args = tuple(self.redact(str(arg)) for arg in record.args)
        return True


class JSONLogFormatter(logging.Formatter):
    """Structured JSON formatter for production log aggregation."""

    def format(self, record: logging.LogRecord) -> str:
        log_obj = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", "-") or "-",
        }
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_obj)


def setup_logging(level: str = "INFO", log_format: str = "text") -> None:
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Clean existing stream handlers to prevent duplicates
    for handler in list(root_logger.handlers):
        if isinstance(handler, logging.StreamHandler):
            root_logger.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    if log_format.lower() == "json":
        formatter = JSONLogFormatter()
    else:
        formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)-7s | [%(request_id)s] %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    handler.setFormatter(formatter)
    handler.addFilter(PIIRedactionFilter())
    root_logger.addHandler(handler)
