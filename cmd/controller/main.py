import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import engine, Base
from routers import heartbeat, nodes, events, invite
import uvicorn

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Fail loud at startup if critical env vars are missing or weak.
    admin_pw = os.environ.get("ADMIN_PASSWORD", "")
    if not admin_pw:
        raise RuntimeError(
            "ADMIN_PASSWORD is not set. Set it in .env before starting the controller."
        )
    if len(admin_pw) < 12:
        raise RuntimeError(
            "ADMIN_PASSWORD is too short (minimum 12 characters)."
        )
    if not os.environ.get("TAILSCALE_API_KEY"):
        log.warning("TAILSCALE_API_KEY is not set — invite provisioning will be unavailable.")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    log.info("Stratus controller started.")
    yield


app = FastAPI(title="Stratus Controller", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(heartbeat.router)
app.include_router(nodes.router)
app.include_router(events.router)
app.include_router(invite.router)


if __name__ == "__main__":
    debug = os.environ.get("DEBUG", "").lower() in ("1", "true", "yes")
    uvicorn.run("main:app", host="0.0.0.0", port=8080, reload=debug)
