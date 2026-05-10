from pydantic import BaseModel
from datetime import datetime
from typing import Optional
import uuid


class HeartbeatPayload(BaseModel):
    node: str
    os: str
    cpu_free_pct: float
    ram_free_mb: int
    container_state: str
    ts: datetime


class EventPayload(BaseModel):
    node: str
    event: str
    ts: datetime


class NodeResponse(BaseModel):
    name: str
    os: str
    tailscale_ip: Optional[str]
    cpu_free_pct: float
    ram_free_mb: int
    container_state: str
    last_seen: datetime
    status: str  # "online" | "offline" — derived, not stored
    created_at: datetime

    class Config:
        from_attributes = True


class EventResponse(BaseModel):
    id: uuid.UUID
    node_name: str
    event: str
    ts: datetime

    class Config:
        from_attributes = True


class InviteCreateRequest(BaseModel):
    node_name: str
    controller_url: str
    idle_threshold_s: float = 120
    cpu_cap_active: float = 0.5
    cpu_cap_idle: float = 2.0
    heartbeat_secs: int = 15


class InviteResponse(BaseModel):
    token: str
    node_name: str
    join_url: str
    expires_at: datetime

    class Config:
        from_attributes = True
