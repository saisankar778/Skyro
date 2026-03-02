import os
import secrets
import string
from typing import Optional, Dict, Any

import boto3
from fastapi import APIRouter, HTTPException, Header
from jose import jwt
import requests
from pydantic import BaseModel
from botocore.exceptions import NoCredentialsError, PartialCredentialsError

router = APIRouter(prefix="/api/auth", tags=["auth"])


AWS_REGION = os.getenv("AWS_REGION")
COGNITO_USER_POOL_ID = os.getenv("COGNITO_USER_POOL_ID")
COGNITO_CLIENT_ID = os.getenv("COGNITO_CLIENT_ID")

if not AWS_REGION:
    AWS_REGION = "ap-south-1"

_cognito = boto3.client("cognito-idp", region_name=AWS_REGION)

_jwks: Optional[Dict[str, Any]] = None


def _get_jwks() -> Dict[str, Any]:
    global _jwks
    if _jwks is not None:
        return _jwks
    if not COGNITO_USER_POOL_ID:
        raise HTTPException(status_code=500, detail="COGNITO_USER_POOL_ID not configured")
    url = f"https://cognito-idp.{AWS_REGION}.amazonaws.com/{COGNITO_USER_POOL_ID}/.well-known/jwks.json"
    res = requests.get(url, timeout=10)
    res.raise_for_status()
    _jwks = res.json()
    return _jwks


def _verify_access_token(token: str) -> Dict[str, Any]:
    jwks = _get_jwks()
    unverified_header = jwt.get_unverified_header(token)
    kid = unverified_header.get("kid")
    key = next((k for k in jwks.get("keys", []) if k.get("kid") == kid), None)
    if not key:
        raise HTTPException(status_code=401, detail="Invalid token")

    if not COGNITO_CLIENT_ID:
        raise HTTPException(status_code=500, detail="COGNITO_CLIENT_ID not configured")

    issuer = f"https://cognito-idp.{AWS_REGION}.amazonaws.com/{COGNITO_USER_POOL_ID}"
    try:
        claims = jwt.decode(
            token,
            key,
            algorithms=[unverified_header.get("alg", "RS256")],
            audience=COGNITO_CLIENT_ID,
            issuer=issuer,
        )
        return claims
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


class AuthStartRequest(BaseModel):
    phone: str


class AuthSignupRequest(BaseModel):
    phone: str


class AuthSignupResponse(BaseModel):
    created: bool


def _random_password(length: int = 24) -> str:
    alphabet = string.ascii_letters + string.digits + "@#%*_-+!"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _require_cognito_client() -> None:
    if not COGNITO_CLIENT_ID:
        raise HTTPException(status_code=503, detail="COGNITO_CLIENT_ID not configured")
    if not COGNITO_USER_POOL_ID:
        raise HTTPException(status_code=503, detail="COGNITO_USER_POOL_ID not configured")


@router.post("/signup", response_model=AuthSignupResponse)
def signup(req: AuthSignupRequest):
    if not COGNITO_USER_POOL_ID:
        raise HTTPException(status_code=500, detail="COGNITO_USER_POOL_ID not configured")

    username = req.phone
    created = False

    try:
        _cognito.admin_create_user(
            UserPoolId=COGNITO_USER_POOL_ID,
            Username=username,
            UserAttributes=[
                {"Name": "phone_number", "Value": req.phone},
            ],
            MessageAction="SUPPRESS",
        )
        created = True
    except _cognito.exceptions.UsernameExistsException:
        created = False
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create user: {e}")

    try:
        _cognito.admin_set_user_password(
            UserPoolId=COGNITO_USER_POOL_ID,
            Username=username,
            Password=_random_password(),
            Permanent=True,
        )
    except Exception:
        pass

    try:
        _cognito.admin_confirm_sign_up(
            UserPoolId=COGNITO_USER_POOL_ID,
            Username=username,
        )
    except Exception:
        pass

    return AuthSignupResponse(created=created)


class AuthStartResponse(BaseModel):
    challengeName: str
    session: Optional[str] = None


@router.post("/start", response_model=AuthStartResponse)
def start_otp(req: AuthStartRequest):
    if not COGNITO_CLIENT_ID or not COGNITO_USER_POOL_ID:
        raise HTTPException(
            status_code=503,
            detail="OTP login not configured (set COGNITO_CLIENT_ID and COGNITO_USER_POOL_ID env vars)",
        )

    try:
        resp = _cognito.initiate_auth(
            ClientId=COGNITO_CLIENT_ID,
            AuthFlow="CUSTOM_AUTH",
            AuthParameters={
                "USERNAME": req.phone,
            },
        )
    except (NoCredentialsError, PartialCredentialsError):
        raise HTTPException(
            status_code=503,
            detail="AWS credentials not configured for Cognito (set AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY or instance role)",
        )
    except _cognito.exceptions.NotAuthorizedException as e:
        raise HTTPException(status_code=401, detail=str(e))
    except _cognito.exceptions.UserNotFoundException:
        raise HTTPException(status_code=404, detail="User not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start OTP: {e}")

    challenge = resp.get("ChallengeName")
    session = resp.get("Session")
    if not challenge:
        raise HTTPException(status_code=500, detail="Cognito did not return a challenge")

    return AuthStartResponse(challengeName=challenge, session=session)


class AuthVerifyRequest(BaseModel):
    phone: str
    code: str
    session: Optional[str] = None
    challengeName: str = "CUSTOM_CHALLENGE"


class AuthTokens(BaseModel):
    accessToken: str
    idToken: str
    refreshToken: Optional[str] = None
    expiresIn: Optional[int] = None
    tokenType: Optional[str] = None


class EmailSignupRequest(BaseModel):
    email: str
    password: str


class EmailConfirmRequest(BaseModel):
    email: str
    code: str


class EmailLoginRequest(BaseModel):
    email: str
    password: str


@router.post("/email/signup")
def email_signup(req: EmailSignupRequest):
    _require_cognito_client()
    try:
        _cognito.sign_up(
            ClientId=COGNITO_CLIENT_ID,
            Username=req.email,
            Password=req.password,
            UserAttributes=[{"Name": "email", "Value": req.email}],
        )
        return {"ok": True}
    except (NoCredentialsError, PartialCredentialsError):
        raise HTTPException(status_code=503, detail="AWS credentials not configured for Cognito")
    except _cognito.exceptions.UsernameExistsException:
        raise HTTPException(status_code=409, detail="User already exists")
    except _cognito.exceptions.InvalidPasswordException as e:
        raise HTTPException(status_code=400, detail=str(e))
    except _cognito.exceptions.InvalidParameterException as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to sign up: {e}")


@router.post("/email/confirm")
def email_confirm(req: EmailConfirmRequest):
    _require_cognito_client()
    try:
        _cognito.confirm_sign_up(
            ClientId=COGNITO_CLIENT_ID,
            Username=req.email,
            ConfirmationCode=req.code,
        )
        return {"ok": True}
    except (NoCredentialsError, PartialCredentialsError):
        raise HTTPException(status_code=503, detail="AWS credentials not configured for Cognito")
    except _cognito.exceptions.CodeMismatchException:
        raise HTTPException(status_code=400, detail="Invalid verification code")
    except _cognito.exceptions.ExpiredCodeException:
        raise HTTPException(status_code=400, detail="Verification code expired")
    except _cognito.exceptions.UserNotFoundException:
        raise HTTPException(status_code=404, detail="User not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to confirm sign up: {e}")


@router.post("/email/login", response_model=AuthTokens)
def email_login(req: EmailLoginRequest):
    _require_cognito_client()
    try:
        resp = _cognito.initiate_auth(
            ClientId=COGNITO_CLIENT_ID,
            AuthFlow="USER_PASSWORD_AUTH",
            AuthParameters={"USERNAME": req.email, "PASSWORD": req.password},
        )
    except (NoCredentialsError, PartialCredentialsError):
        raise HTTPException(status_code=503, detail="AWS credentials not configured for Cognito")
    except _cognito.exceptions.UserNotConfirmedException:
        raise HTTPException(status_code=403, detail="Email not verified")
    except _cognito.exceptions.NotAuthorizedException:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    except _cognito.exceptions.UserNotFoundException:
        raise HTTPException(status_code=404, detail="User not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to login: {e}")

    auth = resp.get("AuthenticationResult")
    if not auth:
        raise HTTPException(status_code=500, detail="Cognito did not return tokens")

    return AuthTokens(
        accessToken=auth.get("AccessToken"),
        idToken=auth.get("IdToken"),
        refreshToken=auth.get("RefreshToken"),
        expiresIn=auth.get("ExpiresIn"),
        tokenType=auth.get("TokenType"),
    )


@router.post("/verify", response_model=AuthTokens)
def verify_otp(req: AuthVerifyRequest):
    if not COGNITO_CLIENT_ID:
        raise HTTPException(status_code=500, detail="COGNITO_CLIENT_ID not configured")

    try:
        resp = _cognito.respond_to_auth_challenge(
            ClientId=COGNITO_CLIENT_ID,
            ChallengeName=req.challengeName,
            Session=req.session,
            ChallengeResponses={
                "USERNAME": req.phone,
                "ANSWER": req.code,
            },
        )
    except _cognito.exceptions.CodeMismatchException:
        raise HTTPException(status_code=400, detail="Invalid OTP")
    except _cognito.exceptions.ExpiredCodeException:
        raise HTTPException(status_code=400, detail="OTP expired")
    except _cognito.exceptions.NotAuthorizedException as e:
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to verify OTP: {e}")

    auth = resp.get("AuthenticationResult")
    if not auth:
        raise HTTPException(status_code=400, detail="OTP verification incomplete; check Cognito challenge configuration")

    return AuthTokens(
        accessToken=auth.get("AccessToken"),
        idToken=auth.get("IdToken"),
        refreshToken=auth.get("RefreshToken"),
        expiresIn=auth.get("ExpiresIn"),
        tokenType=auth.get("TokenType"),
    )


class MeResponse(BaseModel):
    sub: str
    phone: Optional[str] = None


@router.get("/me", response_model=MeResponse)
def me(authorization: Optional[str] = Header(default=None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")

    token = authorization.split(" ", 1)[1].strip()
    claims = _verify_access_token(token)

    return MeResponse(sub=str(claims.get("sub")), phone=claims.get("phone_number"))
