import secrets
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database import get_db
from models import InviteToken
from schemas import InviteCreateRequest, InviteResponse
from datetime import datetime, timezone, timedelta

router = APIRouter()

TOKEN_TTL = timedelta(days=7)


@router.post("/api/v1/invites", response_model=InviteResponse)
async def create_invite(
    body: InviteCreateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    token = secrets.token_urlsafe(24)
    expires_at = datetime.now(timezone.utc) + TOKEN_TTL

    agent_config = {
        "controller_url": body.controller_url,
        "node_name": body.node_name,
        "idle_threshold_s": body.idle_threshold_s,
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


@router.get("/join/{token}")
async def redeem_invite(token: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(InviteToken).where(InviteToken.token == token))
    invite = result.scalar_one_or_none()

    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found")
    if invite.used_at:
        raise HTTPException(status_code=410, detail="Invite already used")
    if invite.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        raise HTTPException(status_code=410, detail="Invite expired")

    invite.used_at = datetime.now(timezone.utc)
    await db.commit()

    # TODO: serve a setup page / install script instead of raw JSON
    return {
        "node_name": invite.node_name,
        "agent_config": invite.agent_config,
        "message": "Setup page coming soon — for now, save agent_config as agent.json",
    }
