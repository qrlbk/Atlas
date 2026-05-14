from app.core.security import create_access_token, decode_access_token, get_password_hash, verify_password


def test_password_hash_roundtrip():
    password = "atlas-secret"
    hashed = get_password_hash(password)
    assert verify_password(password, hashed)
    assert not verify_password("wrong-password", hashed)


def test_jwt_payload():
    token = create_access_token(subject="1", role="school_manager", school_id=7)
    payload = decode_access_token(token)
    assert payload["sub"] == "1"
    assert payload["role"] == "school_manager"
    assert payload["school_id"] == 7
