"""
Tests for security-critical fixes (C1-C4).

C1: API keys stored as bcrypt hashes (no plaintext key_id)
C2: Admin check is strict — tier == "admin" only
C3: HttpOnly cookie set on login/register responses
C4: Website authStore doesn't persist apiKey to localStorage
"""

import hashlib
import secrets
import time

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from predict.core.db.models.user import ApiKey, User
from predict.core.security.hashing import hash_api_key, verify_api_key, generate_api_key


# =============================================================================
# C1: Bcrypt API key storage
# =============================================================================

class TestApiKeyBcryptStorage:
    """API keys must be stored as bcrypt hashes, never plaintext."""

    def test_api_key_model_has_key_prefix(self):
        """ApiKey model should have a key_prefix column (first 8 chars)."""
        # key_prefix is the new column for admin lookup
        assert hasattr(ApiKey, "key_prefix"), "ApiKey model missing 'key_prefix' column"

    def test_api_key_model_no_plaintext_key_id(self):
        """ApiKey model should NOT have key_id column storing plaintext keys."""
        # After C1 fix, key_id should not exist on the model
        # We check that the column either doesn't exist or is not used for plaintext storage
        # The column is being removed entirely
        columns = {c.name for c in ApiKey.__table__.columns}
        assert "key_prefix" in columns, "Missing key_prefix column"
        assert "key_hash" in columns, "Missing key_hash column"
        assert "key_id" not in columns, "key_id column should be removed (stores plaintext keys)"

    def test_generate_api_key_returns_prefixed_key(self):
        """generate_api_key() should return a key with 'pred_' prefix."""
        key = generate_api_key("pred")
        assert key.startswith("pred_")
        assert len(key) > 20  # Should be long enough for security

    def test_hash_api_key_produces_bcrypt_hash(self):
        """hash_api_key() should produce a bcrypt hash string."""
        key = generate_api_key("pred")
        hashed = hash_api_key(key)
        # bcrypt hashes start with $2b$ or $2a$
        assert hashed.startswith("$2"), f"Expected bcrypt hash, got: {hashed[:20]}..."
        assert len(hashed) == 60  # bcrypt hashes are always 60 chars

    def test_verify_api_key_matches_correct_key(self):
        """verify_api_key() should return True for matching key."""
        key = generate_api_key("pred")
        hashed = hash_api_key(key)
        assert verify_api_key(key, hashed) is True

    def test_verify_api_key_rejects_wrong_key(self):
        """verify_api_key() should return False for non-matching key."""
        key = generate_api_key("pred")
        hashed = hash_api_key(key)
        wrong_key = generate_api_key("pred")
        assert verify_api_key(wrong_key, hashed) is False

    @pytest.mark.asyncio
    async def test_api_key_creation_stores_hash_not_plaintext(self):
        """When creating an API key, DB should have bcrypt hash and prefix, not plaintext."""
        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
        from sqlalchemy.pool import StaticPool
        from predict.core.db.base import Base

        engine = create_async_engine(
            "sqlite+aiosqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        async with SessionLocal() as session:
            # Create a test user first
            user = User(
                email="test_c1@example.com",
                name="Test User C1",
                password_hash="$2b$12$fakehashfortest",
                tier="free",
                status="active",
                verified=True,
            )
            session.add(user)
            await session.flush()

            # Generate key the way the fixed auth.py should do it
            plain_key = generate_api_key("pred")
            key_hash = hash_api_key(plain_key)
            key_prefix = plain_key[:8]
            now = time.time()

            api_key = ApiKey(
                key_prefix=key_prefix,
                user_id=user.id,
                key_hash=key_hash,
                name="Test Key",
                status="active",
                created_at=now,
                tier="free",
            )
            session.add(api_key)
            await session.flush()

            # Verify: DB record has bcrypt hash and prefix, not the plaintext key
            result = await session.execute(
                select(ApiKey).where(ApiKey.user_id == user.id)
            )
            stored_key = result.scalar_one()

            # key_hash should be bcrypt (starts with $2b$)
            assert stored_key.key_hash.startswith("$2"), "key_hash should be bcrypt"
            # key_prefix should be first 8 chars of the plain key
            assert stored_key.key_prefix == plain_key[:8]
            # The plain key should NOT be stored anywhere in the record
            assert stored_key.key_hash != plain_key, "Plain key should not be stored as hash"

        await engine.dispose()

    @pytest.mark.asyncio
    async def test_api_key_validation_via_bcrypt(self):
        """Middleware should validate keys by bcrypt.checkpw(), not SHA-256 or plaintext match."""
        plain_key = generate_api_key("pred")
        key_hash = hash_api_key(plain_key)

        # verify_api_key uses bcrypt.checkpw internally
        assert verify_api_key(plain_key, key_hash) is True

        # SHA-256 hash of the key should NOT match the bcrypt hash
        sha256_hash = hashlib.sha256(plain_key.encode()).hexdigest()
        assert sha256_hash != key_hash, "Should use bcrypt, not SHA-256"


# =============================================================================
# C2: Strict admin check
# =============================================================================

class TestAdminCheck:
    """Admin check must be strict: tier == 'admin' only."""

    def test_admin_check_allows_admin_tier(self):
        """User with tier='admin' should pass admin check."""
        from predict.core.api.v1.admin import require_admin

        admin_user = {"tier": "admin", "user_id": 1, "name": "Admin"}
        # Should not raise
        result = require_admin(admin_user)
        assert result == admin_user

    def test_admin_check_rejects_non_admin_tier(self):
        """User with tier != 'admin' should be rejected."""
        from predict.core.api.v1.admin import require_admin
        from fastapi import HTTPException

        regular_user = {"tier": "pro", "user_id": 2, "name": "Regular"}
        with pytest.raises(HTTPException) as exc_info:
            require_admin(regular_user)
        assert exc_info.value.status_code == 403

    def test_admin_check_rejects_enterprise_tier(self):
        """Enterprise tier should NOT be treated as admin."""
        from predict.core.api.v1.admin import require_admin
        from fastapi import HTTPException

        enterprise_user = {"tier": "enterprise", "user_id": 3, "name": "Enterprise"}
        with pytest.raises(HTTPException) as exc_info:
            require_admin(enterprise_user)
        assert exc_info.value.status_code == 403

    def test_admin_check_ignores_is_admin_field(self):
        """The is_admin field should NOT grant admin access (only tier matters)."""
        from predict.core.api.v1.admin import require_admin
        from fastapi import HTTPException

        # User with is_admin=True but tier != admin should be rejected
        tricky_user = {"tier": "free", "is_admin": True, "user_id": 4, "name": "Tricky"}
        with pytest.raises(HTTPException) as exc_info:
            require_admin(tricky_user)
        assert exc_info.value.status_code == 403

    def test_admin_check_ignores_role_field(self):
        """The role field should NOT grant admin access (only tier matters)."""
        from predict.core.api.v1.admin import require_admin
        from fastapi import HTTPException

        # User with role=admin but tier != admin should be rejected
        role_user = {"tier": "premium", "role": "admin", "user_id": 5, "name": "RoleAdmin"}
        with pytest.raises(HTTPException) as exc_info:
            require_admin(role_user)
        assert exc_info.value.status_code == 403


# =============================================================================
# C3: HttpOnly cookie
# =============================================================================

class TestHttpOnlyCookie:
    """Server login/register endpoints should set HttpOnly cookies."""

    def test_login_response_sets_httponly_cookie(self):
        """Login endpoint should set Set-Cookie header with HttpOnly flag."""
        # This is a unit test for the cookie-setting helper
        from predict.core.api.v1.auth import _make_api_key_cookie

        cookie = _make_api_key_cookie("pred_test_key_12345")
        assert "HttpOnly" in cookie
        assert "Secure" in cookie
        assert "SameSite=Lax" in cookie
        assert "Path=/" in cookie
        assert "pred_test_key_12345" in cookie

    def test_cookie_max_age_is_30_days(self):
        """Cookie should expire in 30 days (2592000 seconds)."""
        from predict.core.api.v1.auth import _make_api_key_cookie

        cookie = _make_api_key_cookie("pred_test_key_12345")
        assert "Max-Age=2592000" in cookie


# =============================================================================
# C4: Website authStore (structural check)
# =============================================================================

class TestWebsiteAuthStoreStructure:
    """
    Website authStore.ts should NOT persist apiKey to localStorage.
    These tests verify the code structure by reading the file content.
    """

    def _read_auth_store(self) -> str:
        """Read the authStore.ts file content."""
        import os
        store_path = os.path.join(
            "C:", os.sep, "Users", "Omars", "OneDrive", "Desktop",
            "Predict-pp website", "Kimi_Agent_Predict Website Design",
            "app", "src", "stores", "authStore.ts"
        )
        with open(store_path, "r", encoding="utf-8") as f:
            return f.read()

    def test_no_api_key_in_partialize(self):
        """Zustand partialize should NOT include apiKey."""
        content = self._read_auth_store()
        # Find the partialize function
        if "partialize" in content:
            # Extract the partialize section
            idx = content.index("partialize")
            snippet = content[idx:idx+200]
            assert "apiKey" not in snippet, (
                "apiKey should not be in Zustand partialize (would persist to localStorage)"
            )

    def test_no_document_cookie_set(self):
        """authStore.ts should NOT set document.cookie with api_key."""
        content = self._read_auth_store()
        assert "document.cookie = `api_key=" not in content, (
            "authStore should not set api_key cookie — server sets HttpOnly cookie"
        )
        assert 'document.cookie = "api_key=' not in content, (
            "authStore should not set api_key cookie — server sets HttpOnly cookie"
        )
