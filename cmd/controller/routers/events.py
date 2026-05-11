import logging
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database import get_db
from models import Event
from schemas import EventPayload, EventResponse
from auth import verify_agent_secret, verify_dashboard_token
from typing import List, Optional


def _require_dashboard_token(authorization: str = Header(default="")):
    token = authorization.removeprefix("Bearer ").strip()
    if not token or not verify_dashboard_token(token):
        raise HTTPException(status_code=401, detail="Unauthorized.")

router = APIRouter()
log = logging.getLogger(__name__)


@router.post("/api/v1/events")
async def receive_event(
    payload: EventPayload,
    db: AsyncSession = Depends(get_db),
    x_agent_secret: str = Header(default=""),
):
    if not x_agent_secret or not verify_agent_secret(payload.node, x_agent_secret):
        log.warning("[event] auth failure (node=%s)", payload.node)
        raise HTTPException(status_code=401, detail="Invalid agent secret.")
    event = Event(node_name=payload.node, event=payload.event, ts=payload.ts)
    db.add(event)
    await db.commit()
    print(f"[event] {payload.node} → {payload.event}")
    return {"status": "ok"}


@router.get("/api/v1/events", response_model=List[EventResponse], dependencies=[Depends(_require_dashboard_token)])
async def list_events(
    node: Optional[str] = Query(default=None),
    limit: int = Query(default=100, le=500),
    db: AsyncSession = Depends(get_db),
):
    q = select(Event).order_by(Event.ts.desc()).limit(limit)
    if node:
        q = q.where(Event.node_name == node)
    result = await db.execute(q)
    return result.scalars().all()
