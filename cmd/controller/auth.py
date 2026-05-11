import hmac
import hashlib
import os

_SERVER_SECRET = os.environ.get("SERVER_SECRET", "").encode()


def generate_agent_secret(node_name: str) -> str:
    """Derive a stable per-node secret by HMACing the node name with SERVER_SECRET."""
    return hmac.new(_SERVER_SECRET, node_name.encode(), hashlib.sha256).hexdigest()


def verify_agent_secret(node_name: str, secret: str) -> bool:
    expected = generate_agent_secret(node_name)
    return hmac.compare_digest(expected, secret)
