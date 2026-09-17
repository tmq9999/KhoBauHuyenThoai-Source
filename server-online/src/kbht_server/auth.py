from __future__ import annotations
import hashlib
import base64
import hmac
import secrets
from argon2 import PasswordHasher, extract_parameters, Type
from argon2.exceptions import VerificationError, InvalidHashError
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

PASSWORD_HASHER = PasswordHasher()


def _supported_argon2(encoded: str) -> bool:
    """Bound corrupted stored work factors before entering the native KDF."""
    try:
        parameters = extract_parameters(encoded)
        return (parameters.type == Type.ID and parameters.version == 19 and
                8192 <= parameters.memory_cost <= 65536 and
                1 <= parameters.time_cost <= 3 and 1 <= parameters.parallelism <= 4 and
                parameters.salt_len == 16 and parameters.hash_len == 32)
    except (ValueError, TypeError, InvalidHashError):
        return False

class SessionService:
    def __init__(self, engine, ttl_minutes: int = 60):
        if type(ttl_minutes) is not int or not 1 <= ttl_minutes <= 1440:
            raise ValueError("session TTL must be between 1 and 1440 minutes")
        self.engine = engine
        self.ttl = timedelta(minutes=ttl_minutes)

    @staticmethod
    def _hash(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def issue(self, account_id: UUID) -> str:
        if not isinstance(account_id, UUID):
            raise ValueError("invalid account identity")
        token = secrets.token_urlsafe(32)
        now = datetime.now(timezone.utc)
        with self.engine.begin() as connection:
            account = connection.execute(text("SELECT id FROM accounts WHERE id=:account AND status='ACTIVE' FOR UPDATE"), {"account": account_id}).scalar_one_or_none()
            if account is None:
                raise ValueError("account not found")
            now = datetime.now(timezone.utc)
            connection.execute(text("UPDATE sessions SET revoked_at=:now WHERE account_id=:account AND revoked_at IS NULL"), {"now": now, "account": account_id})
            connection.execute(text("INSERT INTO sessions(id,account_id,token_hash,expires_at) VALUES (:id,:account,:hash,:expires)"), {"id": uuid4(), "account": account_id, "hash": self._hash(token), "expires": now + self.ttl})
        return token

    def resolve(self, token: str) -> UUID | None:
        if not isinstance(token, str) or not 20 <= len(token) <= 256:
            return None
        with self.engine.begin() as connection:
            row = connection.execute(text("SELECT s.account_id FROM sessions s JOIN accounts a ON a.id=s.account_id WHERE s.token_hash=:hash AND s.revoked_at IS NULL AND s.expires_at > now() AND a.status='ACTIVE'"), {"hash": self._hash(token)}).scalar_one_or_none()
            return row

    def revoke(self, token: str) -> None:
        with self.engine.begin() as connection:
            connection.execute(text("UPDATE sessions SET revoked_at=now() WHERE token_hash=:hash AND revoked_at IS NULL"), {"hash": self._hash(token)})

class AccountService:
    def __init__(self, engine):
        self.engine = engine

    @staticmethod
    def _normalize(login: str) -> str:
        if not isinstance(login, str):
            raise ValueError("login is required")
        value = login.strip().casefold()
        if not 3 <= len(value) <= 128 or any(ch.isspace() for ch in value):
            raise ValueError("invalid login")
        return value

    @staticmethod
    def _password_hash(password: str) -> str:
        if not isinstance(password, str) or not 8 <= len(password) <= 128:
            raise ValueError("password must be 8-128 characters")
        return PASSWORD_HASHER.hash(password)

    @classmethod
    def _verify(cls, password: str, encoded: str) -> bool:
        if not isinstance(password, str) or not 8 <= len(password) <= 128 or not isinstance(encoded, str):
            return False
        try:
            if encoded.startswith('$argon2id$'):
                return _supported_argon2(encoded) and PASSWORD_HASHER.verify(encoded, password)
            if not encoded.startswith('scrypt$'):
                return False
            _, salt_text, digest_text = encoded.split('$')
            salt = base64.b64decode(salt_text, altchars=b'-_', validate=True)
            expected = base64.b64decode(digest_text, altchars=b'-_', validate=True)
            if len(salt) != 16 or len(expected) != 64:
                return False
            actual = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
            return hmac.compare_digest(actual, expected)
        except (ValueError, TypeError, VerificationError, InvalidHashError):
            return False

    def register(self, login: str, password: str) -> UUID:
        normalized = self._normalize(login)
        password_hash = self._password_hash(password)
        with self.engine.begin() as connection:
            account_id = uuid4()
            try:
                connection.execute(text("INSERT INTO accounts(id, normalized_login, password_hash) VALUES (:id,:login,:password)"), {"id": account_id, "login": normalized, "password": password_hash})
            except IntegrityError as error:
                if getattr(error.orig, 'sqlstate', None) == '23505':
                    raise ValueError("login already exists") from None
                raise
        return account_id

    def authenticate(self, login: str, password: str) -> UUID | None:
        try:
            normalized = self._normalize(login)
        except ValueError:
            return None
        with self.engine.begin() as connection:
            row = connection.execute(text("SELECT id, password_hash FROM accounts WHERE normalized_login=:login AND status='ACTIVE'"), {"login": normalized}).mappings().one_or_none()
        if row is None or not self._verify(password, row['password_hash']):
            return None
        encoded = row['password_hash']
        replacement = self._password_hash(password) if encoded.startswith('scrypt$') or PASSWORD_HASHER.check_needs_rehash(encoded) else encoded
        # Compare-and-set under the account lock: concurrent password changes or
        # locks must not be overwritten by an older successful verification.
        with self.engine.begin() as connection:
            current = connection.execute(text("SELECT password_hash,status FROM accounts WHERE id=:id FOR UPDATE"), {'id': row['id']}).mappings().one_or_none()
            if current is None or current['status'] != 'ACTIVE':
                return None
            if current['password_hash'] != encoded:
                return row['id'] if self._verify(password, current['password_hash']) else None
            if replacement != encoded:
                connection.execute(text('UPDATE accounts SET password_hash=:hash WHERE id=:id'), {'hash': replacement, 'id': row['id']})
            return row['id']
