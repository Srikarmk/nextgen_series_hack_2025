import os
import logging
import sys
from loguru import logger
from typing import Any
import re

# Ensure the logs directory exists
os.makedirs("logs", exist_ok=True)

def format_log_message(record):
    """Extract class name from message and format it properly with fixed width"""
    message = record.get("message", "")
    # Updated regex to allow dots in component names like [OSRM.get_osrm_road_geometry]
    class_name_match = re.search(r'\[([A-Za-z_][A-Za-z0-9_.]*)\]', message)

    if class_name_match:
        class_name = class_name_match.group(1)
        clean_message = re.sub(r'\[([A-Za-z_][A-Za-z0-9_.]*)\]\s*', '', message)
        # Pad class name to fixed width of 24 characters for proper alignment
        padded_class_name = f"{class_name:<24}"
        record["extra"]["class_name"] = padded_class_name
        record["extra"]["clean_message"] = clean_message
        record["extra"]["class_name_separator"] = " | "
        return True
    else:
        # Try to extract class/function name from call stack or module context
        # Get function name from record (Loguru provides this)
        func_name = record.get("function", "")
        module_name = record.get("name", "")
        
        # Extract class/function from module path (e.g., "app.services.geocoding" -> "Geocoding")
        display_name = None
        
        # Get module parts (e.g., ["app", "services", "geocoding"])
        module_parts = module_name.split(".") if module_name else []
        
        # Find the last meaningful module part (skip "app", "api", "endpoints", "services", etc.)
        skip_parts = {"app", "api", "endpoints", "services", "utils", "extractors", "clients", "database"}
        last_meaningful_part = None
        for part in reversed(module_parts):
            if part and part not in skip_parts:
                last_meaningful_part = part
                break
        
        # Capitalize first letter to make it class-like (e.g., "geocoding" -> "Geocoding")
        if last_meaningful_part:
            class_like_name = last_meaningful_part[0].upper() + last_meaningful_part[1:] if len(last_meaningful_part) > 0 else last_meaningful_part
        else:
            class_like_name = module_parts[-1] if module_parts else "Unknown"
        
        # Use only function name if available (user wants just function name, not Module.function)
        # Only fall back to module name if no function name is available
        if func_name and func_name != "<module>":
            # Use just the function name (e.g., "try_geocode_variants" instead of "Geocoding.try_geocode_variants")
            display_name = func_name
        else:
            # Fallback: use class-like name if no function name available
            display_name = class_like_name
        
        # Pad to fixed width
        padded_class_name = f"{display_name:<24}"
        record["extra"]["class_name"] = padded_class_name
        record["extra"]["clean_message"] = message
        record["extra"]["class_name_separator"] = " | "
        return True

# Remove default Loguru handler to avoid duplicates
logger.remove()

# Configure Loguru Logger - Use a single rotating log file
# Rotates daily at midnight, preventing new files on every app restart
# Old files are automatically compressed and cleaned up after retention period
logger.add(
    "logs/app.log",  # Single log file that rotates automatically
    rotation="00:00",  # Rotate daily at midnight (one file per day)
    retention="7 days",  # Keep only 7 days of logs (reduced from 10)
    compression="zip",  # Compress old log files to save space
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
           "<level>{level: <8}</level> | "
           "<cyan>{file}</cyan>:<cyan>{name}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    serialize=False,
    enqueue=True,
    level="DEBUG"  # Log everything to file
)

# Add clean console handler - FILTERED for readability
def get_simple_module_name(record):
    """Extract simple module name from full module path"""
    module_name = record.get("name", "")
    if not module_name:
        return "unknown"
    
    # Split module path and get last meaningful part
    parts = module_name.split(".")
    # Skip "app" prefix if present
    if len(parts) > 1 and parts[0] == "app":
        parts = parts[1:]
    
    # Return last part (e.g., "uploads" from "app.api.endpoints.uploads")
    return parts[-1] if parts else module_name

def console_filter(record):
    """Filter and format console logs"""
    # First apply the basic filters
    if not (record["level"].no >= 20 and  # INFO level and above
            not record["name"].startswith("pymongo") and  # Filter out MongoDB logs
            not record["name"] == "logging" and  # Filter out logging module debug messages
            not record["name"].startswith("passlib") and  # Filter out passlib logs
            not record["name"].startswith("kafka") and  # Filter out Kafka verbose logs
            not record["name"].startswith("httpx") and  # Filter out httpx logs
            not record["name"].startswith("httpcore") and  # Filter out httpcore logs
            not record["name"].startswith("urllib3")):  # Filter out urllib3 logs
        return False

    # Format the message to extract class name
    format_log_message(record)
    
    # Add simplified module name to record
    record["extra"]["simple_module"] = get_simple_module_name(record)
    return True

logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{extra[class_name]}</level>{extra[class_name_separator]}<cyan>{extra[simple_module]}</cyan> - <level>{extra[clean_message]}</level>",
    level="INFO",
    filter=console_filter
)

# Configure standard Python logging to redirect to Loguru
class InterceptHandler(logging.Handler):
    def emit(self, record):
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        # Get the logger name and format it as class name
        logger_name = record.name if record.name else "root"

        # Format the message with class name in brackets (e.g., [werkzeug])
        formatted_message = f"[{logger_name}] {record.getMessage()}"

        logger.opt(depth=depth, exception=record.exc_info).log(level, formatted_message)

# Replace standard logging handlers with Loguru interceptor
logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)

# Ensure uvicorn and werkzeug logs are captured
for name in ["uvicorn", "uvicorn.access", "uvicorn.error", "fastapi", "werkzeug"]:
    werkzeug_logger = logging.getLogger(name)
    werkzeug_logger.handlers = [InterceptHandler()]
    werkzeug_logger.setLevel(logging.INFO)
    werkzeug_logger.propagate = False

# Reduce logging verbosity for various modules
for name in [
    "pymongo", "pymongo.command", "pymongo.connection", "pymongo.server", "pymongo.topology",
    "passlib", "passlib.handlers", "passlib.handlers.bcrypt",
    "asyncio", "asyncio.selector_events",
    "kafka", "kafka.conn", "kafka.consumer", "kafka.coordinator", "kafka.producer",
    "httpx", "httpcore", "urllib3"
]:
    logging.getLogger(name).setLevel(logging.WARNING)

# Set root logger to INFO to reduce general debug noise
logging.getLogger().setLevel(logging.INFO)


class AppLogger:
    """Logging class using Loguru for structured logging. Provides synchronous and asynchronous logging capabilities."""

    def __init__(self) -> None:
        pass

    def log_info(self, *args: Any, **kwargs: Any) -> None:
        """Logs an info message."""
        level = kwargs.pop("level", "INFO")
        message = " ".join(map(str, args))
        logger.opt(depth=1).log(level, message, **kwargs)

    async def async_log_info(self, *args: Any, **kwargs: Any) -> None:
        """Logs an info message asynchronously."""
        level = kwargs.pop("level", "INFO")
        message = " ".join(map(str, args))
        logger.opt(depth=1).log(level, message, **kwargs)

    def log_error(self, *args: Any, **kwargs: Any) -> None:
        """Logs an error message."""
        message = " ".join(map(str, args))
        logger.opt(depth=1).error(message, **kwargs)

    async def async_log_error(self, *args: Any, **kwargs: Any) -> None:
        """Logs an error message asynchronously."""
        message = " ".join(map(str, args))
        logger.opt(depth=1).error(message, **kwargs)

    def log_debug(self, *args: Any, **kwargs: Any) -> None:
        """Logs a debug message."""
        message = " ".join(map(str, args))
        logger.opt(depth=1).debug(message, **kwargs)

    async def async_log_debug(self, *args: Any, **kwargs: Any) -> None:
        """Logs a debug message asynchronously."""
        message = " ".join(map(str, args))
        logger.opt(depth=1).debug(message, **kwargs)

    def log_warning(self, *args: Any, **kwargs: Any) -> None:
        """Logs a warning message."""
        message = " ".join(map(str, args))
        logger.opt(depth=1).warning(message, **kwargs)

    async def async_log_warning(self, *args: Any, **kwargs: Any) -> None:
        """Logs a warning message asynchronously."""
        message = " ".join(map(str, args))
        logger.opt(depth=1).warning(message, **kwargs)


# Instantiate global logger instance
app_logger = AppLogger()