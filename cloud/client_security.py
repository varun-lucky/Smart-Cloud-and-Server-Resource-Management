"""Authentication for API clients; tokens map to stable client identities."""
import hmac
import json
import os
from functools import wraps

from flask import g, jsonify, request


def client_required(fn):
    @wraps(fn)
    def inner(*args, **kwargs):
        try:
            parsed = json.loads(os.getenv("CLIENT_TOKENS_JSON", "{}"))
            clients = parsed if isinstance(parsed, dict) else {}
        except (TypeError, ValueError):
            clients = {}
        supplied = request.headers.get("Authorization", "")
        token = supplied[7:].strip() if supplied.lower().startswith("bearer ") else ""
        identity = next((str(name) for name, expected in clients.items()
                         if isinstance(expected, str) and hmac.compare_digest(token.encode("utf-8"), expected.encode("utf-8"))), None)
        if not identity or identity in ("", "None"):
            return jsonify({"error": "unauthorized client"}), 401
        g.client_id = identity
        return fn(*args, **kwargs)
    return inner
