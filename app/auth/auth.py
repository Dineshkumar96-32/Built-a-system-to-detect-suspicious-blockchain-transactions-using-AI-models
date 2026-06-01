"""Authentication compatibility wrapper for app/auth/auth.py."""
from auth.auth import (
    Role,
    TokenData,
    TokenPair,
    create_token_pair,
    decode_token,
    hash_password,
    verify_password,
    get_current_user,
    require_role,
    RATE_LIMIT_RPM,
)
