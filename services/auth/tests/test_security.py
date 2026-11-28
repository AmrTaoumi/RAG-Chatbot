import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

import security


@pytest.fixture(scope="module")
def key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def claims(**overrides):
    now = int(time.time())
    base = {"sub": "u123", "email": "a@lancaster.ac.uk", "iat": now, "exp": now + 900, "jti": "t789"}
    base.update(overrides)
    return base


def test_hash_is_argon2_and_not_plaintext():
    h = security.hash_password("correct horse")
    assert h.startswith("$argon2id$")
    assert "correct horse" not in h


def test_verify_accepts_right_password_and_rejects_wrong_one():
    h = security.hash_password("correct horse")
    assert security.verify_password(h, "correct horse") is True
    assert security.verify_password(h, "wrong horse") is False


def test_same_password_gives_different_hashes():
    assert security.hash_password("correct horse") != security.hash_password("correct horse")


def test_access_token_round_trip(key):
    token = security.create_access_token(key, "u123", "a@lancaster.ac.uk")
    decoded = security.decode_access_token(key.public_key(), token)
    assert decoded["sub"] == "u123"
    assert decoded["email"] == "a@lancaster.ac.uk"
    assert decoded["exp"] - decoded["iat"] == 900
    assert decoded["jti"]
    assert jwt.get_unverified_header(token)["alg"] == "RS256"


def test_each_token_gets_its_own_jti(key):
    a = security.decode_access_token(key.public_key(), security.create_access_token(key, "u123", "a@x.com"))
    b = security.decode_access_token(key.public_key(), security.create_access_token(key, "u123", "a@x.com"))
    assert a["jti"] != b["jti"]


def test_expired_token_rejected(key):
    now = int(time.time())
    token = jwt.encode(claims(iat=now - 1000, exp=now - 100), key, algorithm="RS256")
    with pytest.raises(jwt.ExpiredSignatureError):
        security.decode_access_token(key.public_key(), token)


def test_tampered_token_rejected(key):
    header, _, signature = security.create_access_token(key, "u123", "a@x.com").split(".")
    forged_payload = jwt.encode(claims(sub="someone-else"), key, algorithm="RS256").split(".")[1]
    with pytest.raises(jwt.InvalidSignatureError):
        security.decode_access_token(key.public_key(), f"{header}.{forged_payload}.{signature}")


def test_token_signed_with_another_key_rejected(key):
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    token = jwt.encode(claims(), other, algorithm="RS256")
    with pytest.raises(jwt.InvalidSignatureError):
        security.decode_access_token(key.public_key(), token)


def test_alg_none_token_rejected(key):
    token = jwt.encode(claims(), None, algorithm="none")
    with pytest.raises(jwt.InvalidAlgorithmError):
        security.decode_access_token(key.public_key(), token)


@pytest.mark.parametrize("missing", ["sub", "exp", "iat", "jti"])
def test_token_missing_a_required_claim_rejected(key, missing):
    payload = claims()
    del payload[missing]
    token = jwt.encode(payload, key, algorithm="RS256")
    with pytest.raises(jwt.MissingRequiredClaimError):
        security.decode_access_token(key.public_key(), token)


def test_refresh_token_hash_is_stable_and_not_the_token():
    token, token_hash = security.new_refresh_token()
    assert token_hash == security.hash_refresh_token(token)
    assert token not in token_hash
    assert len(token_hash) == 64


def test_refresh_tokens_are_random():
    assert security.new_refresh_token()[0] != security.new_refresh_token()[0]


def test_access_token_header_has_kid_of_the_signing_key(key):
    token = security.create_access_token(key, "u123", "a@x.com")
    assert jwt.get_unverified_header(token)["kid"] == security.key_id(key.public_key())


def test_key_id_is_the_same_for_the_same_key_and_different_for_another(key):
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    assert security.key_id(key.public_key()) == security.key_id(key.public_key())
    assert security.key_id(key.public_key()) != security.key_id(other.public_key())
    assert len(security.key_id(key.public_key())) == 16