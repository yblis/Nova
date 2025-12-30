from __future__ import annotations

import contextlib
import json
from typing import Iterator, Any, Dict

from redis import Redis


class ProgressBus:
    def __init__(self, redis: Redis):
        self.redis = redis

    def _channel(self, job_id: str) -> str:
        return f"progress:{job_id}"

    def publish(self, job_id: str, data: Dict[str, Any]) -> None:
        try:
            msg = json.dumps(data)
            self.redis.publish(self._channel(job_id), msg)
            # Store last status with 1 hour TTL
            self.redis.setex(f"job_status:{job_id}", 3600, msg)
        except Exception as e:
            # Silently ignore Redis errors during publish
            # This allows the application to continue working even if Redis is down
            pass
            
    def get_last_status(self, job_id: str) -> Dict[str, Any] | None:
        """Retrieve the last published status for a job."""
        try:
            data = self.redis.get(f"job_status:{job_id}")
            if data:
                if isinstance(data, (bytes, bytearray)):
                    data = data.decode("utf-8")
                return json.loads(data)
        except Exception:
            pass
        return None

    @contextlib.contextmanager
    def subscribe(self, job_id: str) -> Iterator[Iterator[str]]:
        try:
            pubsub = self.redis.pubsub()
            pubsub.subscribe(self._channel(job_id))
            try:
                def _iter() -> Iterator[str]:
                    try:
                        for msg in pubsub.listen():
                            if msg.get("type") != "message":
                                continue
                            data = msg.get("data")
                            if isinstance(data, (bytes, bytearray)):
                                yield data.decode("utf-8", "ignore")
                            elif isinstance(data, str):
                                yield data
                    except Exception:
                        # If Redis connection is lost during iteration, stop yielding
                        return
                yield _iter()
            finally:
                try:
                    pubsub.close()
                except Exception:
                    pass  # Ignore errors when closing pubsub
        except Exception:
            # If we can't even subscribe, yield an empty iterator
            def _empty_iter() -> Iterator[str]:
                return
                yield  # This line is never reached but needed for the function to be a generator
            yield _empty_iter()

