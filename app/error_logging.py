import logging
import sys
from pathlib import Path
from typing import Iterable


PROJECT_ROOT = Path(__file__).resolve().parent.parent
ERROR_LOG = PROJECT_ROOT / "error.txt"


class ErrorOnlyFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return record.levelno >= logging.ERROR


def configure_error_logging() -> None:
    """Route all ERROR+ logs to stderr and project-root error.txt.

    Uvicorn may install its own handlers before importing the app. This function
    adds only the two Calimara-specific sinks and is safe to call multiple times
    under reload/import cycles.
    """
    root = logging.getLogger()
    root.setLevel(logging.INFO)

    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    if not _has_handler(root.handlers, logging.StreamHandler, stream=sys.stderr):
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setLevel(logging.ERROR)
        console_handler.addFilter(ErrorOnlyFilter())
        console_handler.setFormatter(formatter)
        root.addHandler(console_handler)

    if not _has_file_handler(root.handlers, ERROR_LOG):
        file_handler = logging.FileHandler(ERROR_LOG, encoding="utf-8")
        file_handler.setLevel(logging.ERROR)
        file_handler.addFilter(ErrorOnlyFilter())
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)


def _has_handler(
    handlers: Iterable[logging.Handler],
    handler_type: type[logging.Handler],
    *,
    stream=None,
) -> bool:
    for handler in handlers:
        if isinstance(handler, handler_type):
            if stream is None or getattr(handler, "stream", None) is stream:
                return True
    return False


def _has_file_handler(handlers: Iterable[logging.Handler], path: Path) -> bool:
    target = str(path.resolve())
    for handler in handlers:
        if isinstance(handler, logging.FileHandler):
            try:
                if str(Path(handler.baseFilename).resolve()) == target:
                    return True
            except OSError:
                continue
    return False
