import os
from functools import wraps
from flask import request, jsonify
def supplied():
    a = request.headers.get("Authorization", "")
    return a[7:].strip() if a.lower().startswith("bearer ") else request.headers.get("X-API-Token", "").strip()
def _guard(env_name, label):
    def deco(fn):
        @wraps(fn)
        def inner(*args, **kwargs):
            expected = os.getenv(env_name, "CHANGE_ME")
            if not expected or expected == "CHANGE_ME" or supplied() != expected:
                return jsonify({"error": "unauthorized " + label}), 401
            return fn(*args, **kwargs)
        return inner
    return deco
admin_required = _guard("ADMIN_TOKEN", "admin")
worker_required = _guard("WORKER_SHARED_TOKEN", "worker")
