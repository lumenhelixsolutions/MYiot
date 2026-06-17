import pytest
from auth.session import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
)


def test_password_hash_round_trip():
    hashed = hash_password("secret")
    assert verify_password("secret", hashed)
    assert not verify_password("wrong", hashed)


def test_jwt_round_trip():
    token = create_access_token("admin", "admin")
    payload = decode_access_token(token)
    assert payload["sub"] == "admin"
    assert payload["role"] == "admin"
