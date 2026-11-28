import hashlib
import secrets
import time
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from cryptography.hazmat.primitives import serialization
# Argon2 adds a salt which are random extra characters mixed in each time
# so the same password gives a different hash every time
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

ACCESS_TOKEN_SECONDS = 900
REFRESH_TOKEN_DAYS = 7

_hasher = PasswordHasher()

# used when the email is unknown, so login takes the same time either way
DUMMY_HASH = _hasher.hash("not-a-real-password") # defence for hackers 


def hash_password(password):
    return _hasher.hash(password)


def verify_password(password_hash, password):
    try:
        return _hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False


def key_id(public_key):
    der = public_key.public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return hashlib.sha256(der).hexdigest()[:16]

def create_access_token(private_key, user_id, email):
    now = int(time.time())
    payload = {
        "sub": user_id,
        "email": email,
        "iat": now,
        "exp": now + ACCESS_TOKEN_SECONDS,
        "jti": str(uuid.uuid4()),
    }
    kid = key_id(private_key.public_key())
    return jwt.encode(payload, private_key, algorithm="RS256", headers={"kid": kid}) #  stamps it with the private key.


def decode_access_token(public_key, token): # checks the stamp against the public key and gives abck the payloud
    return jwt.decode(
        token,
        public_key,
        algorithms=["RS256"],
        options={"require": ["sub", "exp", "iat", "jti"]},
    )


def hash_refresh_token(token):
    return hashlib.sha256(token.encode()).hexdigest() # use sha 256 its fast and the same input always gives the same hash


def new_refresh_token():
    token = secrets.token_urlsafe(32)
    return token, hash_refresh_token(token) # one for the user and th eother is ofr the db 


def refresh_expiry():
    return datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_DAYS)
