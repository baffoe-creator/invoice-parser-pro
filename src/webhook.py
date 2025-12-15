"""Webhook sender intended to be enqueued to RQ worker."""
import os
import json
import time
import hmac
import hashlib
import requests
from typing import Dict, Any

MAX_ATTEMPTS = int(os.getenv("MAX_WEBHOOK_RETRIES", "5"))
BACKOFF_BASE = 2  # exponential backoff base

def sign_payload(secret: str, payload_bytes: bytes) -> str:
    sig = hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()
    return f"sha256={sig}"

def send_webhook(payload: Dict[str, Any], url: str, secret: str = None):
    """
    This function runs in the worker process (RQ).
    It will attempt up to MAX_ATTEMPTS with exponential backoff.
    """
    body = json.dumps(payload).encode("utf-8")
    signature = sign_payload(secret or os.getenv("SECRET_KEY", "secret"), body)
    headers = {
        "Content-Type": "application/json",
        "X-Hub-Signature-256": signature
    }
    attempt = 0
    while attempt < MAX_ATTEMPTS:
        attempt += 1
        try:
            r = requests.post(url, data=body, headers=headers, timeout=10)
            if 200 <= r.status_code < 300:
                return {"ok": True, "status_code": r.status_code}
            if 400 <= r.status_code < 500:
                return {"ok": False, "status_code": r.status_code, "error": r.text}
        except Exception as e:
            # log in real app; simple sleep & retry here
            pass
        sleep_time = min(300, BACKOFF_BASE ** attempt)
        time.sleep(sleep_time)
    return {"ok": False, "status_code": None}