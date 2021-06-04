from flask import g, has_request_context
from functools import wraps


def _get_function_hash(function_or_method):
    f = function_or_method
    if function_or_method.__class__ == "method":
        f = function_or_method.__func__
    return hash(f)


def cache_at_request_scope(f):
    missing = object()

    @wraps(f)
    def wrapped(*args, **kwargs):
        if not has_request_context():
            return f(*args, **kwargs)

        caches = g.get("function_caches", None)
        if not caches:
            g.function_caches = caches = {}

        f_hash = _get_function_hash(f)
        f_cache = caches.get(f_hash, None)

        if not f_cache:
            g.function_caches[f_hash] = f_cache = {}

        cache_key = args
        for item in sorted(kwargs.items(), key=lambda t: t[0]):
            cache_key += item

        cached_value = f_cache.get(cache_key, missing)
        if cached_value is not missing:
            print(f"Cache hit for {f} and key {cache_key}")
            return cached_value

        value = f(*args, **kwargs)
        f_cache[cache_key] = value
        return value

    return wrapped
