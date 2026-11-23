import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from fastapi.testclient import TestClient

import main


def private_pem(key):
    return key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )


def public_pem(key):
    return key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )


@pytest.fixture(scope="module")
def rsa_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture
def write(tmp_path):
    def _write(data):
        path = tmp_path / "key.pem"
        path.write_bytes(data)
        return str(path)
    return _write


def test_loads_rsa_private_key(rsa_key, write):
    key = main.load_private_key(write(private_pem(rsa_key)))
    assert isinstance(key, rsa.RSAPrivateKey)
    assert key.private_numbers() == rsa_key.private_numbers()


@pytest.mark.parametrize("path", [None, ""])
def test_rejects_unset_path(path):
    with pytest.raises(RuntimeError, match="JWT_PRIVATE_KEY_PATH is not set"):
        main.load_private_key(path)


def test_rejects_missing_file(tmp_path):
    with pytest.raises(RuntimeError, match="cannot read"):
        main.load_private_key(str(tmp_path / "nope.pem"))


@pytest.mark.parametrize("data", [b"not a key", b""])
def test_rejects_garbage(write, data):
    with pytest.raises(RuntimeError, match="not a valid"):
        main.load_private_key(write(data))


def test_rejects_public_key(rsa_key, write):
    with pytest.raises(RuntimeError, match="not a valid"):
        main.load_private_key(write(public_pem(rsa_key)))


def test_rejects_encrypted_key(rsa_key, write):
    pem = rsa_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.BestAvailableEncryption(b"secret"),
    )
    with pytest.raises(RuntimeError, match="not a valid unencrypted"):
        main.load_private_key(write(pem))


def test_rejects_non_rsa_key(write):
    ec_key = ec.generate_private_key(ec.SECP256R1())
    with pytest.raises(RuntimeError, match="not an RSA key"):
        main.load_private_key(write(private_pem(ec_key)))


def test_rejects_short_key(write):
    short = rsa.generate_private_key(public_exponent=65537, key_size=1024)
    with pytest.raises(RuntimeError, match="at least 2048 bits"):
        main.load_private_key(write(private_pem(short)))


def test_startup_fails_without_key(monkeypatch):
    monkeypatch.delenv("JWT_PRIVATE_KEY_PATH", raising=False)
    with pytest.raises(RuntimeError, match="JWT_PRIVATE_KEY_PATH is not set"):
        with TestClient(main.app):
            pass
