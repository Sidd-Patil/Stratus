import hmac
import hashlib
import json
import os
import subprocess
from typing import TypedDict, Literal
from fastapi import Header, HTTPException, Request

_SERVER_SECRET = os.environ.get("SERVER_SECRET", "").encode()
_ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")


def generate_agent_secret(node_name: str) -> str:
    return hmac.new(_SERVER_SECRET, node_name.encode(), hashlib.sha256).hexdigest()


def verify_agent_secret(node_name: str, secret: str) -> bool:
    expected = generate_agent_secret(node_name)
    return hmac.compare_digest(expected, secret)


def generate_dashboard_token() -> str:
    """Deterministic session token — valid as long as SERVER_SECRET doesn't change."""
    return hmac.new(_SERVER_SECRET, b"dashboard_session", hashlib.sha256).hexdigest()


def verify_dashboard_token(token: str) -> bool:
    return hmac.compare_digest(generate_dashboard_token(), token)


def verify_admin_password(password: str) -> bool:
    return hmac.compare_digest(_ADMIN_PASSWORD, password)


class CallerInfo(TypedDict):
    role: Literal["admin", "user"]
    identity: str  # "admin" | Tailscale LoginName (e.g. user@example.com)


def tailscale_whois(ip: str) -> str | None:
    """Return the Tailscale LoginName for a given Tailscale IP, or None."""
    try:
        r = subprocess.run(
            ["tailscale", "whois", "--json", ip],
            capture_output=True, text=True, timeout=2,
        )
        if r.returncode != 0:
            return None
        return json.loads(r.stdout).get("UserProfile", {}).get("LoginName")
    except Exception:
        return None


async def get_caller(
    request: Request,
    authorization: str = Header(default=""),
) -> CallerInfo:
    """FastAPI dependency — resolves the caller as admin (Bearer token) or user (Tailscale whois)."""
    token = authorization.removeprefix("Bearer ").strip()
    if token and verify_dashboard_token(token):
        return CallerInfo(role="admin", identity="admin")

    client_ip = request.client.host if request.client else None
    if client_ip:
        identity = tailscale_whois(client_ip)
        if identity:
            return CallerInfo(role="user", identity=identity)

    raise HTTPException(status_code=401, detail="Unauthorized.")
