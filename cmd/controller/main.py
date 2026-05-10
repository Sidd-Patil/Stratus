# cmd/controller/main.py
# Minimal FastAPI controller for Stratus
# Receives heartbeats and events from agents, stores in memory for now.

from fastapi import FastAPI
from pydantic import BaseModel
from datetime import datetime
from typing import Optional
import uvicorn

app = FastAPI(title="Stratus Controller")

# In-memory store — will move to PostgreSQL in Phase 2
nodes: dict = {}
events: list = []


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


@app.post("/api/v1/heartbeat")
def receive_heartbeat(payload: HeartbeatPayload):
    nodes[payload.node] = {
        "os": payload.os,
        "cpu_free_pct": payload.cpu_free_pct,
        "ram_free_mb": payload.ram_free_mb,
        "container_state": payload.container_state,
        "last_seen": payload.ts,
    }
    print(f"[heartbeat] {payload.node} | CPU free: {payload.cpu_free_pct:.1f}% | RAM free: {payload.ram_free_mb}MB | {payload.container_state}")
    return {"status": "ok"}


@app.post("/api/v1/events")
def receive_event(payload: EventPayload):
    events.append(payload)
    print(f"[event] {payload.node} → {payload.event}")
    return {"status": "ok"}


@app.get("/api/v1/nodes")
def list_nodes():
    return nodes


@app.get("/api/v1/events")
def list_events():
    return events


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8080, reload=True)