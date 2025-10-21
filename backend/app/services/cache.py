import os
import json
from typing import Any, Optional

import redis


class RedisCache:
    def __init__(self):
        host = os.getenv("REDIS_HOST", "redis")
        port = int(os.getenv("REDIS_PORT", "6379"))
        self.client = redis.Redis(host=host, port=port, decode_responses=True)

    def get_json(self, key: str) -> Optional[Any]:
        data = self.client.get(key)
        if data is None:
            return None
        return json.loads(data)

    def set_json(self, key: str, value: Any, ex: Optional[int] = 3600) -> None:
        self.client.set(key, json.dumps(value), ex=ex)

