"""Redis helper singleton and convenience functions."""
import os
import json
import redis
from typing import Optional, Dict, Any

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
redis_client = redis.from_url(REDIS_URL, decode_responses=True)

def set_json(key: str, value: Dict[str, Any], ex: Optional[int] = None):
    redis_client.set(key, json.dumps(value))
    if ex:
        redis_client.expire(key, ex)

def get_json(key: str) -> Optional[Dict[str, Any]]:
    raw = redis_client.get(key)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None

def setex_json(key: str, value: Dict[str, Any], ex: int):
    redis_client.setex(key, ex, json.dumps(value))

def delete_key(key: str):
    redis_client.delete(key)

def hset(key: str, mapping: Dict[str, Any]):
    redis_client.hset(key, mapping=mapping)

def hgetall(key: str) -> Dict[str, Any]:
    return redis_client.hgetall(key) or {}