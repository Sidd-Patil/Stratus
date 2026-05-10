from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database import get_db
from models import Event
from schemas import EventPayload, EventResponse
from typing import List, Optional

router = APIRouter()


@router.post("/api/v1/events")
async def receive_event(payload: EventPayload, db: AsyncSession = Depends(get_db)):
    event = Event(node_name=payload.node, event=payload.event, ts=payload.ts)
    db.add(event)
    await db.commit()
    print(f"[event] {payload.node} → {payload.event}")
    return {"status": "ok"}


@router.get("/api/v1/events", response_model=List[EventResponse])
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
