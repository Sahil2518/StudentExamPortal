from pydantic import BaseModel, Field, EmailStr
from typing import Optional


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    user: Optional[dict] = None


class ForgotPasswordRequest(BaseModel):
    email: EmailStr = Field(..., description="Registered account email address")


class ForgotPasswordResponse(BaseModel):
    message: str
    email: str
    expires_in_minutes: int = 10
    delivery_status: str
    dev_otp: Optional[str] = None


class VerifyOTPRequest(BaseModel):
    email: EmailStr = Field(..., description="Registered account email address")
    otp: str = Field(..., min_length=6, max_length=6, description="6-digit verification code")


class VerifyOTPResponse(BaseModel):
    message: str
    reset_token: str


class ResetPasswordRequest(BaseModel):
    email: EmailStr = Field(..., description="Registered account email address")
    reset_token: str = Field(..., description="Signed token obtained from /verify-otp")
    new_password: str = Field(..., min_length=6, max_length=72, description="New account password")


class ResetPasswordResponse(BaseModel):
    message: str
