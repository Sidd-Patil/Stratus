import logging
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database import get_db
from models import Node
from schemas import HeartbeatPayload
from auth import verify_agent_secret

router = APIRouter()
log = logging.getLogger(__name__)


@router.post("/api/v1/heartbeat")
async def receive_heartbeat(
    payload: HeartbeatPayload,
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_agent_secret: str = Header(default=""),
):
    if not x_agent_secret or not verify_agent_secret(payload.node, x_agent_secret):
        log.warning("[heartbeat] auth failure from %s (node=%s)", request.client, payload.node)
        raise HTTPException(status_code=401, detail="Invalid agent secret.")
    tailscale_ip = request.client.host if request.client else None

    result = await db.execute(select(Node).where(Node.name == payload.node))
    node = result.scalar_one_or_none()

    if node is None:
        node = Node(
            name=payload.node,
            os=payload.os,
            tailscale_ip=tailscale_ip,
            cpu_free_pct=payload.cpu_free_pct,
            ram_free_mb=payload.ram_free_mb,
            container_state=payload.container_state,
            last_seen=payload.ts,
        )
        db.add(node)
    else:
        node.os = payload.os
        node.tailscale_ip = tailscale_ip
        node.cpu_free_pct = payload.cpu_free_pct
        node.ram_free_mb = payload.ram_free_mb
        node.container_state = payload.container_state
        node.last_seen = payload.ts

    await db.commit()
    print(f"[heartbeat] {payload.node} | CPU free: {payload.cpu_free_pct:.1f}% | RAM free: {payload.ram_free_mb}MB | {payload.container_state}")
    return {"status": "ok"}
