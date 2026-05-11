from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from database import get_db
from models import Node, Event
from schemas import NodeResponse
from datetime import datetime, timezone, timedelta
from typing import List
import os

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")

router = APIRouter()

OFFLINE_AFTER = timedelta(seconds=45)


def _node_to_response(node: Node) -> NodeResponse:
    age = datetime.now(timezone.utc) - node.last_seen.replace(tzinfo=timezone.utc)
    return NodeResponse(
        name=node.name,
        os=node.os,
        tailscale_ip=node.tailscale_ip,
        cpu_free_pct=node.cpu_free_pct,
        ram_free_mb=node.ram_free_mb,
        container_state=node.container_state,
        last_seen=node.last_seen,
        status="online" if age < OFFLINE_AFTER else "offline",
        created_at=node.created_at,
    )


@router.get("/api/v1/nodes", response_model=List[NodeResponse])
async def list_nodes(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Node).order_by(Node.name))
    return [_node_to_response(n) for n in result.scalars().all()]


class NodeDeleteRequest(BaseModel):
    admin_password: str


@router.delete("/api/v1/nodes/{name}")
async def delete_node(name: str, body: NodeDeleteRequest, db: AsyncSession = Depends(get_db)):
    if not ADMIN_PASSWORD or body.admin_password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid admin password.")

    result = await db.execute(select(Node).where(Node.name == name))
    node = result.scalar_one_or_none()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found.")

    await db.execute(delete(Event).where(Event.node_name == name))
    await db.execute(delete(Node).where(Node.name == name))
    await db.commit()
    return {"deleted": name}
