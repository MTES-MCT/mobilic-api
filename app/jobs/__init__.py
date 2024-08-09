from functools import wraps
from app import app


def log_execution(func):
    @wraps(func)  # This preserves the original function's metadata
    def wrapper(*args, **kwargs):
        app.logger.info(f"Beginning task {func.__name__}")
        result = func(*args, **kwargs)  # Execute the original function
        app.logger.info(f"Ending task {func.__name__}")
        return result

    return wrapper
