"""Reusable authentication strategies for connector authors."""
from __future__ import annotations

import base64
import time

import httpx

from app.core.redis import get_redis
from app.integration.errors import SourceAuthError, SourceUnavailableError


def basic_auth_header(username: str, password: str) -> dict[str, str]:
    token = base64.b64encode(f"{username}:{password}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


class ClientCredentialsTokenProvider:
    """OAuth2 client-credentials flow with a shared (Redis) token cache."""

    def __init__(self, cache_key: str, token_url: str, client_id: str, client_secret: str, timeout: float = 3.0):
        self.cache_key = f"connector:token:{cache_key}"
        self.token_url = token_url
        self.client_id = client_id
        self.client_secret = client_secret
        self.timeout = timeout
        self._local: tuple[str, float] | None = None

    def token(self) -> str:
        cached = self._cached()
        if cached:
            return cached
        try:
            resp = httpx.post(
                self.token_url,
                data={"grant_type": "client_credentials", "client_id": self.client_id, "client_secret": self.client_secret},
                timeout=self.timeout,
            )
        except httpx.TimeoutException as exc:
            raise SourceUnavailableError("Token endpoint timed out") from exc
        except httpx.TransportError as exc:
            raise SourceUnavailableError("Token endpoint unreachable") from exc
        if resp.status_code >= 500:
            raise SourceUnavailableError(f"Token endpoint unavailable (HTTP {resp.status_code})", http_status=resp.status_code)
        if resp.status_code != 200:
            raise SourceAuthError(f"Token request rejected (HTTP {resp.status_code})", http_status=resp.status_code)
        body = resp.json()
        token, ttl = body["access_token"], int(body.get("expires_in", 300))
        self._store(token, max(30, ttl - 30))
        return token

    def invalidate(self) -> None:
        self._local = None
        try:
            get_redis().delete(self.cache_key)
        except Exception:
            pass

    def _cached(self) -> str | None:
        try:
            value = get_redis().get(self.cache_key)
            if value:
                return value
        except Exception:
            pass
        if self._local and self._local[1] > time.time():
            return self._local[0]
        return None

    def _store(self, token: str, ttl: int) -> None:
        self._local = (token, time.time() + ttl)
        try:
            get_redis().set(self.cache_key, token, ex=ttl)
        except Exception:
            pass
