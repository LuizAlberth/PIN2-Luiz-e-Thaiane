import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from .db import session
from .models import User

SECRET = os.getenv('APP_SECRET', '')
if not SECRET:
    SECRET = secrets.token_urlsafe(32)  # local development only; set APP_SECRET for stable sessions
bearer = HTTPBearer(auto_error=False)

def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 600_000)
    return f'{salt.hex()}:{digest.hex()}'

def verify_password(password: str, stored: str) -> bool:
    try:
        salt, digest = stored.split(':')
        actual = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), 600_000)
        return hmac.compare_digest(actual, bytes.fromhex(digest))
    except (ValueError, TypeError):
        return False

def sign(user_id: str) -> str:
    body = base64.urlsafe_b64encode(json.dumps({'sub': user_id, 'exp': int(time.time()) + 8 * 3600}).encode()).rstrip(b'=')
    signature = hmac.new(SECRET.encode(), body, hashlib.sha256).digest()
    return f'{body.decode()}.{base64.urlsafe_b64encode(signature).rstrip(b"=").decode()}'

def current_admin(credentials: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(session)) -> User:
    if not credentials:
        raise HTTPException(401, 'Autenticação necessária')
    try:
        body, sig = credentials.credentials.split('.')
        actual = hmac.new(SECRET.encode(), body.encode(), hashlib.sha256).digest()
        expected = base64.urlsafe_b64decode(sig + '=' * (-len(sig) % 4))
        data = json.loads(base64.urlsafe_b64decode(body + '=' * (-len(body) % 4)))
        if not hmac.compare_digest(actual, expected) or data['exp'] < time.time():
            raise ValueError('invalid token')
        user = db.get(User, data['sub'])
        if not user or not user.active or user.role != 'ADMIN':
            raise ValueError('inactive or unauthorized')
        return user
    except (ValueError, KeyError, TypeError):
        raise HTTPException(401, 'Sessão inválida ou expirada') from None
