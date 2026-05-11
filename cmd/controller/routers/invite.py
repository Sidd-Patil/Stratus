import json
import logging
import os
import secrets
import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database import get_db
from models import InviteToken
from schemas import InviteCreateRequest, InviteResponse
from auth import generate_agent_secret
from datetime import datetime, timezone, timedelta

router = APIRouter()
log = logging.getLogger(__name__)

TOKEN_TTL = timedelta(days=7)

ADMIN_PASSWORD    = os.environ.get("ADMIN_PASSWORD", "")
TAILSCALE_API_KEY = os.environ.get("TAILSCALE_API_KEY", "")
TAILSCALE_TAILNET = os.environ.get("TAILSCALE_TAILNET", "-")

# Raw bash script template.
# __TS_KEY__, __NODE_NAME__, __CONFIG_JSON__ are replaced server-side before serving.
# All other $VARIABLES expand at runtime on the target machine.
_INSTALL_SCRIPT = r"""#!/usr/bin/env bash
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; BLUE='\033[0;34m'; NC='\033[0m'
log()     { echo -e "${BLUE}[stratus]${NC} $*"; }
success() { echo -e "${GREEN}[stratus]${NC} $*"; }
err()     { echo -e "${RED}[stratus]${NC} $*"; exit 1; }

TS_AUTH_KEY="__TS_KEY__"
NODE_NAME="__NODE_NAME__"
GITHUB_REPO="Sidd-Patil/Stratus"
INSTALL_DIR="/usr/local/bin"
CONFIG_DIR="$HOME/.stratus"

# ── Detect platform ───────────────────────────────────────────────────────────
OS=$(uname -s | tr '[:upper:]' '[:lower:]')
ARCH=$(uname -m)
case "$ARCH" in
  x86_64)        ARCH="amd64" ;;
  aarch64|arm64) ARCH="arm64" ;;
  *) err "Unsupported architecture: $ARCH" ;;
esac
log "Platform: $OS/$ARCH"

# ── Docker ────────────────────────────────────────────────────────────────────
if ! command -v docker &>/dev/null; then
  if [ "$OS" = "linux" ]; then
    log "Docker not found — installing..."
    curl -fsSL https://get.docker.com | sh
    sudo usermod -aG docker "$USER"
    log "Docker installed. You may need to log out and back in for group permissions."
  else
    err "Docker not found. Install OrbStack (https://orbstack.dev) or Docker Desktop, then re-run this script."
  fi
else
  log "Docker: $(docker --version)"
fi

# ── Tailscale ─────────────────────────────────────────────────────────────────
if ! command -v tailscale &>/dev/null; then
  if [ "$OS" = "linux" ]; then
    log "Tailscale not found — installing..."
    curl -fsSL https://tailscale.com/install.sh | sh
  else
    err "Tailscale not found. Install from https://tailscale.com/download, then re-run this script."
  fi
else
  log "Tailscale: found"
fi

log "Connecting to Tailscale..."
sudo tailscale up --authkey="$TS_AUTH_KEY" --accept-routes

# ── Agent binary ──────────────────────────────────────────────────────────────
BINARY_URL="https://github.com/$GITHUB_REPO/releases/latest/download/stratus-$OS-$ARCH"
log "Downloading Stratus agent ($OS/$ARCH)..."
sudo curl -fsSL "$BINARY_URL" -o "$INSTALL_DIR/stratus"
sudo chmod +x "$INSTALL_DIR/stratus"

# ── Config ────────────────────────────────────────────────────────────────────
mkdir -p "$CONFIG_DIR"
cat > "$CONFIG_DIR/agent.json" <<'STRATUS_CONFIG'
__CONFIG_JSON__
STRATUS_CONFIG

# ── Service ───────────────────────────────────────────────────────────────────
if [ "$OS" = "linux" ]; then
  sudo tee /etc/systemd/system/stratus.service >/dev/null <<STRATUS_SERVICE
[Unit]
Description=Stratus Agent
After=network-online.target docker.service tailscaled.service
Wants=network-online.target

[Service]
ExecStart=/usr/local/bin/stratus ${CONFIG_DIR}/agent.json
Restart=on-failure
RestartSec=5
User=$USER

[Install]
WantedBy=multi-user.target
STRATUS_SERVICE
  sudo systemctl daemon-reload
  sudo systemctl enable stratus
  sudo systemctl start stratus

else
  PLIST="$HOME/Library/LaunchAgents/dev.stratus.agent.plist"
  mkdir -p "$HOME/Library/LaunchAgents"
  cat > "$PLIST" <<STRATUS_PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>dev.stratus.agent</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/stratus</string>
        <string>${CONFIG_DIR}/agent.json</string>
    </array>
    <key>RunAtLoad</key><true/>
    <key>KeepAlive</key><true/>
    <key>StandardOutPath</key><string>$HOME/Library/Logs/stratus.log</string>
    <key>StandardErrorPath</key><string>$HOME/Library/Logs/stratus.log</string>
</dict>
</plist>
STRATUS_PLIST
  launchctl load "$PLIST"
fi

success "Done! '$NODE_NAME' will appear in the Stratus dashboard within 15 seconds."
"""


async def _mint_tailscale_key() -> str:
    """Generate a one-time preauthorized Tailscale auth key via the Tailscale API.
    The key is never stored — it is generated on demand and served once."""
    if not TAILSCALE_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="Tailscale provisioning is not configured on this controller.",
        )
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"https://api.tailscale.com/api/v2/tailnet/{TAILSCALE_TAILNET}/keys",
            headers={"Authorization": f"Bearer {TAILSCALE_API_KEY}"},
            json={
                "capabilities": {
                    "devices": {
                        "create": {
                            "reusable": False,
                            "ephemeral": False,
                            "preauthorized": True,
                        }
                    }
                },
                "expirySeconds": int(TOKEN_TTL.total_seconds()),
            },
            timeout=10,
        )
    if resp.status_code != 200:
        # Log the real error server-side; return a generic message to the client.
        log.error("Tailscale API error %s: %s", resp.status_code, resp.text)
        raise HTTPException(
            status_code=502,
            detail="Failed to provision Tailscale key. Check controller logs.",
        )
    return resp.json()["key"]


@router.post("/api/v1/invites", response_model=InviteResponse)
async def create_invite(
    body: InviteCreateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    if not ADMIN_PASSWORD or body.admin_password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid admin password.")

    token = secrets.token_urlsafe(24)
    expires_at = datetime.now(timezone.utc) + TOKEN_TTL

    # Tailscale key is NOT stored — it is minted fresh when the script is fetched.
    agent_config = {
        "controller_url": body.controller_url,
        "node_name": body.node_name,
        "agent_secret": generate_agent_secret(body.node_name),
        "idle_threshold_s": body.idle_threshold_s,
        "cpu_idle_threshold_pct": body.cpu_idle_threshold_pct,
        "cpu_cap_active": body.cpu_cap_active,
        "cpu_cap_idle": body.cpu_cap_idle,
        "heartbeat_secs": body.heartbeat_secs,
    }

    invite = InviteToken(
        token=token,
        node_name=body.node_name,
        agent_config=agent_config,
        expires_at=expires_at,
    )
    db.add(invite)
    await db.commit()

    base = str(request.base_url).rstrip("/")
    return InviteResponse(
        token=token,
        node_name=body.node_name,
        join_url=f"{base}/join/{token}",
        expires_at=expires_at,
    )


@router.get("/join/{token}/script", response_class=PlainTextResponse)
async def get_install_script(token: str, db: AsyncSession = Depends(get_db)):
    # Lock the row to prevent two simultaneous requests both getting a valid token.
    result = await db.execute(
        select(InviteToken).where(InviteToken.token == token).with_for_update()
    )
    invite = result.scalar_one_or_none()

    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found.")
    if invite.used_at:
        raise HTTPException(status_code=410, detail="Invite already used.")
    if invite.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        raise HTTPException(status_code=410, detail="Invite expired.")

    # Mint the Tailscale key now — generated fresh, served once, never persisted.
    ts_key = await _mint_tailscale_key()

    # Mark as used before returning so a second request cannot reuse the token.
    invite.used_at = datetime.now(timezone.utc)
    await db.commit()

    config_json = json.dumps(invite.agent_config, indent=2)

    script = (
        _INSTALL_SCRIPT
        .replace("__TS_KEY__", ts_key)
        .replace("__NODE_NAME__", invite.node_name)
        .replace("__CONFIG_JSON__", config_json)
    )
    return PlainTextResponse(content=script, media_type="text/x-shellscript")


@router.get("/join/{token}")
async def get_invite_page_data(token: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(InviteToken).where(InviteToken.token == token))
    invite = result.scalar_one_or_none()

    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found.")
    if invite.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        raise HTTPException(status_code=410, detail="Invite expired.")

    return {
        "node_name": invite.node_name,
        "agent_config": invite.agent_config,
    }
