"""
utils/decorators.py
Decoradores útiles
"""
import time
import functools

def timer(func):
    """Decorador para medir tiempo de ejecución"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        end = time.time()
        print(f"⏱️ {func.__name__}: {end - start:.3f}s")
        return result
    return wrapper

def retry(max_attempts=3, delay=1):
    """Decorador para reintentar en caso de error"""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            attempts = 0
            while attempts < max_attempts:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    attempts += 1
                    if attempts == max_attempts:
                        raise
                    time.sleep(delay)
            return None
        return wrapper
    return decorator
