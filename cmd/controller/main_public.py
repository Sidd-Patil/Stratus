import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import engine, Base
from routers import invite, login

log = logging.getLogger(__name__)

_ALLOWED_ORIGIN = os.environ.get("ALLOWED_ORIGIN", "*")


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not os.environ.get("ADMIN_PASSWORD"):
        raise RuntimeError("ADMIN_PASSWORD is not set.")
    if len(os.environ.get("ADMIN_PASSWORD", "")) < 12:
        raise RuntimeError("ADMIN_PASSWORD is too short (minimum 12 characters).")
    if not os.environ.get("SERVER_SECRET") or len(os.environ.get("SERVER_SECRET", "")) < 32:
        raise RuntimeError(
            "SERVER_SECRET is not set or too short (minimum 32 characters). "
            "Generate one with: python3 -c \"import secrets; print(secrets.token_hex(32))\""
        )
    if not os.environ.get("TAILSCALE_API_KEY"):
        log.warning("TAILSCALE_API_KEY is not set — invite provisioning will be unavailable.")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    log.info("Stratus public controller started.")
    yield


app = FastAPI(title="Stratus Public Controller", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[_ALLOWED_ORIGIN] if _ALLOWED_ORIGIN != "*" else ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(invite.router)
app.include_router(login.router)
