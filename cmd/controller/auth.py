import hmac
import hashlib
import os

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
