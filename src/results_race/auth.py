"""HTTP Basic auth check, constant-time."""
import base64
import hmac


def authorized(header, expected):
    """header: the Authorization header value; expected: 'user:password'. No configured login means nobody gets in."""
    if not expected or not header or not header.startswith("Basic "):
        return False
    try:
        given = base64.b64decode(header[6:], validate=True)
    except ValueError:
        return False
    return hmac.compare_digest(given, expected.encode())
