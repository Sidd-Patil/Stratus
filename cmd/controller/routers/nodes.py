from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database import get_db
from models import Node
from schemas import NodeResponse
from datetime import datetime, timezone, timedelta
from typing import List

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
