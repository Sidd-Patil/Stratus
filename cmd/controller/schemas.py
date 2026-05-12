from pydantic import BaseModel
from pydantic import StringConstraints
from typing import Annotated, Optional
from datetime import datetime
import uuid

# Shared constrained types
NodeName = Annotated[str, StringConstraints(
    strip_whitespace=True,
    min_length=1,
    max_length=63,
    pattern=r'^[a-zA-Z0-9][a-zA-Z0-9_-]*$',  # no leading dash/underscore, safe for shell
)]
ShortStr  = Annotated[str, StringConstraints(min_length=1, max_length=128)]
EventStr  = Annotated[str, StringConstraints(min_length=1, max_length=64)]


class HeartbeatPayload(BaseModel):
    node:            NodeName
    os:              ShortStr
    cpu_free_pct:    float
    ram_free_mb:     int
    container_state: ShortStr
    ts:              datetime


class EventPayload(BaseModel):
    node:  NodeName
    event: EventStr
    ts:    datetime


class NodeResponse(BaseModel):
    name:            str
    owner:           Optional[str]
    os:              str
    tailscale_ip:    Optional[str]
    cpu_free_pct:    float
    ram_free_mb:     int
    container_state: str
    last_seen:       datetime
    status:          str       # "online" | "offline" — derived, not stored
    created_at:      datetime

    class Config:
        from_attributes = True


class EventResponse(BaseModel):
    id:        uuid.UUID
    node_name: str
    event:     str
    ts:        datetime

    class Config:
        from_attributes = True


class InviteCreateRequest(BaseModel):
    node_name:            NodeName
    controller_url:       ShortStr
    admin_password:       str       # validated server-side, not length-constrained
    owner_ts_identity:    Optional[str] = None   # Tailscale LoginName of the machine owner
    idle_threshold_s:     float = 120
    cpu_idle_threshold_pct: float = 15.0
    cpu_cap_active:       float = 0.5
    cpu_cap_idle:         float = 2.0
    heartbeat_secs:       int   = 15


class CallerResponse(BaseModel):
    role:     str   # "admin" | "user"
    identity: str   # "admin" | Tailscale LoginName


class InviteResponse(BaseModel):
    token:      str
    node_name:  str
    join_url:   str
    expires_at: datetime

    class Config:
        from_attributes = True
