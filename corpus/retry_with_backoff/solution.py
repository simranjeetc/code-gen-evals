import time
from functools import wraps


def retry_with_backoff(exceptions, attempts, base_delay=0.1, max_delay=10.0, sleep=time.sleep):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(1, attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as error:
                    last_error = error
                    if attempt == attempts:
                        raise
                    delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
                    sleep(delay)
            raise last_error

        return wrapper

    return decorator
