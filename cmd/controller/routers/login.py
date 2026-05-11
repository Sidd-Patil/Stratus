from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from auth import verify_admin_password, generate_dashboard_token

router = APIRouter()


class LoginRequest(BaseModel):
    password: str


@router.post("/api/v1/auth/login")
async def login(body: LoginRequest):
    if not verify_admin_password(body.password):
        raise HTTPException(status_code=401, detail="Invalid password.")
    return {"token": generate_dashboard_token()}
