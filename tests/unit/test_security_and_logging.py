import logging

from app.core.logging import PIIRedactionFilter
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_password_hashing():
    raw_pass = "SuperSecurePassword123!"
    hashed = hash_password(raw_pass)

    assert hashed != raw_pass
    assert verify_password(raw_pass, hashed) is True
    assert verify_password("WrongPassword!", hashed) is False


def test_jwt_token_roundtrip():
    token = create_access_token(
        subject="user_12345",
        role="DISPATCHER",
        extra_claims={"tenant": "metro_atlanta"},
    )
    payload = decode_access_token(token)

    assert payload["sub"] == "user_12345"
    assert payload["role"] == "DISPATCHER"
    assert payload["tenant"] == "metro_atlanta"
    assert "exp" in payload


def test_pii_redaction_filter():
    filter_obj = PIIRedactionFilter()

    # Test phone redaction
    msg_with_phone = "Customer called from +1 (404) 555-0183 regarding leak"
    record1 = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=1,
        msg=msg_with_phone,
        args=(),
        exc_info=None,
    )
    filter_obj.filter(record1)
    assert "[REDACTED_PHONE]" in record1.msg
    assert "+1 (404) 555-0183" not in record1.msg

    # Test email redaction
    msg_with_email = "User profile created for test.customer@gmail.com"
    record2 = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=1,
        msg=msg_with_email,
        args=(),
        exc_info=None,
    )
    filter_obj.filter(record2)
    assert "[REDACTED_EMAIL]" in record2.msg
    assert "test.customer@gmail.com" not in record2.msg

    # Test token and password redaction
    msg_with_secret = 'Incoming request password="SecretPass123" Bearer eyJhbGciOiJIUzI1Ni...'
    record3 = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=1,
        msg=msg_with_secret,
        args=(),
        exc_info=None,
    )
    filter_obj.filter(record3)
    assert "[REDACTED_SECRET]" in record3.msg
    assert "SecretPass123" not in record3.msg
    assert "[REDACTED_TOKEN]" in record3.msg
