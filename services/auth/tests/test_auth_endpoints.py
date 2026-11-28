import uuid

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

import main
import security

EMAIL = "student@lancaster.ac.uk"
PASSWORD = "correct horse"


class FakeStore:
    #Stands in for the database, so these tests run in CI without Postgres

    def __init__(self):
        self.users = {}
        self.refresh_tokens = []

    def create_user(self, conn, email, password_hash):
        if any(u["email"] == email for u in self.users.values()):
            return None
        user_id = str(uuid.uuid4())
        self.users[user_id] = {"id": user_id, "email": email, "password_hash": password_hash}
        return user_id

    def get_user_by_email(self, conn, email):
        return next((u for u in self.users.values() if u["email"] == email), None)

    def get_user_by_id(self, conn, user_id):
        user = self.users.get(user_id)
        return {"id": user["id"], "email": user["email"]} if user else None

    def save_refresh_token(self, conn, user_id, token_hash, expires_at):
        self.refresh_tokens.append({"user_id": user_id, "token_hash": token_hash, "expires_at": expires_at})


@pytest.fixture(scope="module")
def key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture
def db(monkeypatch, key):
    fake = FakeStore()
    for name in ("create_user", "get_user_by_email", "get_user_by_id", "save_refresh_token"):
        monkeypatch.setattr(main.store, name, getattr(fake, name))
    monkeypatch.setattr(main.app.state, "private_key", key, raising=False)
    main.app.dependency_overrides[main.get_conn] = lambda: None
    yield fake
    main.app.dependency_overrides.clear()


@pytest.fixture
def client(db):
    return TestClient(main.app)


def register(client, email=EMAIL, password=PASSWORD):
    return client.post("/auth/register", json={"email": email, "password": password})


def login(client, email=EMAIL, password=PASSWORD):
    return client.post("/auth/login", json={"email": email, "password": password})


# register

def test_register_returns_201_with_user_id_and_email(client, db):
    r = register(client)
    assert r.status_code == 201
    body = r.json()
    assert body["email"] == EMAIL
    assert body["user_id"] in db.users


def test_register_lowercases_email(client):
    r = register(client, email="Student@Lancaster.AC.UK")
    assert r.json()["email"] == EMAIL


@pytest.mark.parametrize("second", [EMAIL, "STUDENT@lancaster.ac.uk"])
def test_register_duplicate_email_returns_409(client, second):
    register(client)
    r = register(client, email=second)
    assert r.status_code == 409


def test_register_short_password_returns_422(client):
    assert register(client, password="short").status_code == 422


def test_register_invalid_email_returns_422(client):
    assert register(client, email="not-an-email").status_code == 422


def test_register_stores_only_a_password_hash(client, db):
    register(client)
    (user,) = db.users.values()
    assert user["password_hash"] != PASSWORD
    assert PASSWORD not in user["password_hash"]
    assert security.verify_password(user["password_hash"], PASSWORD)


# login

def test_login_returns_access_token(client, key):
    register(client)
    r = login(client)
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 900
    claims = security.decode_access_token(key.public_key(), body["access_token"])
    assert claims["email"] == EMAIL


def test_login_sets_refresh_cookie_with_safe_flags(client):
    register(client)
    r = login(client)
    cookie = r.headers["set-cookie"].lower()
    assert cookie.startswith("refresh_token=")
    assert "httponly" in cookie
    assert "samesite=strict" in cookie
    assert "path=/auth" in cookie
    assert "max-age=604800" in cookie


def test_login_stores_only_the_refresh_token_hash(client, db):
    register(client)
    r = login(client)
    token = r.cookies["refresh_token"]
    (saved,) = db.refresh_tokens
    assert saved["token_hash"] == security.hash_refresh_token(token)
    assert saved["token_hash"] != token


def test_login_is_case_insensitive_on_email(client):
    register(client)
    assert login(client, email="STUDENT@Lancaster.ac.uk").status_code == 200


def test_wrong_password_and_unknown_email_get_the_same_401(client):
    register(client)
    wrong_password = login(client, password="wrong horse")
    unknown_email = login(client, email="nobody@lancaster.ac.uk")
    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json() == unknown_email.json()


def test_failed_login_sets_no_cookie(client, db):
    register(client)
    r = login(client, password="wrong horse")
    assert "set-cookie" not in r.headers
    assert db.refresh_tokens == []


# /auth/me

def test_me_with_valid_token_returns_user(client):
    user_id = register(client).json()["user_id"]
    token = login(client).json()["access_token"]
    r = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json() == {"user_id": user_id, "email": EMAIL}


def test_me_without_token_returns_401(client):
    r = client.get("/auth/me")
    assert r.status_code == 401
    assert r.headers["www-authenticate"] == "Bearer"


def test_me_with_garbage_token_returns_401(client):
    r = client.get("/auth/me", headers={"Authorization": "Bearer not-a-token"})
    assert r.status_code == 401


def test_me_for_deleted_user_returns_401(client, db):
    register(client)
    token = login(client).json()["access_token"]
    db.users.clear()
    r = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401
