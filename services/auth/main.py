import logging
import os
import sys
from contextlib import asynccontextmanager

import psycopg
import jwt 

from psycopg.rows import dict_row
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import Depends, FastAPI, HTTPException, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr, Field
from fastapi.middleware.cors import CORSMiddleware

import security
import store

logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format='{"time": "%(asctime)s", "level": "%(levelname)s", "message": "%(message)s"}',
)
logger = logging.getLogger(__name__)


def parse_origins(raw: str | None) -> list[str]:
    origins = [o.strip().rstrip("/") for o in (raw or "").split(",") if o.strip()]
    if "*" in origins:
        raise RuntimeError("CORS_ALLOWED_ORIGINS must list explicit origins, '*' is not allowed")
    if not origins:
        raise RuntimeError("CORS_ALLOWED_ORIGINS is not set")
    return origins


ALLOWED_ORIGINS = parse_origins(os.getenv("CORS_ALLOWED_ORIGINS"))
logger.info(f"CORS allowed origins: {ALLOWED_ORIGINS}")

MIN_KEY_BITS = 2048


def load_private_key(path: str | None) -> rsa.RSAPrivateKey:
    if not path:
        raise RuntimeError("JWT_PRIVATE_KEY_PATH is not set")
    try:
        with open(path, "rb") as f:
            key = serialization.load_pem_private_key(f.read(), password=None)
    except OSError as e:
        raise RuntimeError(f"cannot read JWT private key at {path}: {e.strerror}") from e
    except (ValueError, TypeError) as e:
        raise RuntimeError(f"JWT private key at {path} is not a valid unencrypted PEM private key") from e
    if not isinstance(key, rsa.RSAPrivateKey):
        raise RuntimeError(f"JWT private key at {path} is not an RSA key")
    if key.key_size < MIN_KEY_BITS:
        raise RuntimeError(f"JWT private key at {path} must be at least {MIN_KEY_BITS} bits")
    return key


@asynccontextmanager
async def lifespan(app):
    app.state.private_key = load_private_key(os.getenv("JWT_PRIVATE_KEY_PATH"))
    logger.info("JWT private key loaded")
    with psycopg.connect(os.environ["DATABASE_URL"], connect_timeout=10) as conn:
        store.ensure_tables(conn)
    logger.info("auth tables ready")
    yield


class RegisterRequest(BaseModel): # request model 
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel): #  bad login always gets 401
    email: str = Field(max_length=254)
    password: str = Field(max_length=128)

def get_conn(): # connection to database 
    with psycopg.connect(os.environ["DATABASE_URL"], row_factory=dict_row) as conn:
        yield conn

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/auth/register", status_code=201)
def register(body: RegisterRequest, conn=Depends(get_conn)):  # get_conn gives this function the database connection
    email = body.email.lower()
    user_id = store.create_user(conn, email, security.hash_password(body.password))
    if user_id is None:
        raise HTTPException(409, "email already registered")
    logger.info(f"user registered: {user_id}")
    return {"user_id": user_id, "email": email}


INVALID_LOGIN = "invalid email or password"

#httpbearer means token reader 
bearer = HTTPBearer(auto_error= False)

def unauthorized(detail):
    return HTTPException(401,detail, headers={"WWW-Authenticate" : "Bearer"})


@app.get ("/auth/me")
def me (credentials: HTTPAuthorizationCredentials | None = Depends (bearer) , conn= Depends (get_conn)):
    #  1 no tokens sent 
    if credentials is  None:
        raise unauthorized("not authorized")
 #   2 check the stamp , the expiry and the required fields 
    try:
        claims = security.decode_access_token(app.state.private_key.public_key(), credentials.credentials)
    except jwt.InvalidTokenError:
            raise unauthorized("invalid token")

    # 3 find the user the token belongs to
    user = store.get_user_by_id(conn, claims["sub"])
    if user is None:
        raise unauthorized("invalid token")
    return {"user_id": user["id"], "email": user["email"]}



@app.post("/auth/login")
def login(body: LoginRequest, response: Response, conn=Depends(get_conn)):
    # 1 check email plus password
    user = store.get_user_by_email(conn, body.email.lower())
    password_hash = user["password_hash"] if user else security.DUMMY_HASH
    valid = security.verify_password(password_hash, body.password)
    if user is None or not valid:
        raise HTTPException(401, INVALID_LOGIN)

    # 2 make the access token
    access_token = security.create_access_token(app.state.private_key, user["id"], user["email"])

    # 3 make the refresh token, save only its hash
    refresh_token, refresh_hash = security.new_refresh_token()
    store.save_refresh_token(conn, user["id"], refresh_hash, security.refresh_expiry())

    # 4 give the refresh token to the browser in a cookie
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        samesite="strict",
        path="/auth",
        max_age=security.REFRESH_TOKEN_DAYS * 24 * 3600, # 7 days 
    )
    logger.info(f"user logged in: {user['id']}")
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": security.ACCESS_TOKEN_SECONDS,
    }