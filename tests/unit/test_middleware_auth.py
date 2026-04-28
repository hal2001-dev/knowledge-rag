"""TASK-019 Phase B (a) — Clerk JWT 실 검증 단위 테스트.

자체 RSA 키쌍으로 가짜 JWKS를 만들고, AuthMiddleware._verify_token이
서명·만료·issuer 분기를 정확히 처리하는지 회귀.
"""
from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from apps.config import Settings
from apps.middleware.auth import AuthMiddleware


@pytest.fixture(scope="module")
def rsa_keypair() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture
def settings_phase2() -> Settings:
    return Settings(
        openai_api_key="sk-test",
        auth_enabled=True,
        clerk_jwks_url="https://example.clerk.accounts.dev/.well-known/jwks.json",
        clerk_issuer="https://example.clerk.accounts.dev",
    )


def _make_token(
    private_key: rsa.RSAPrivateKey,
    *,
    sub: str = "user_abc123",
    iss: str = "https://example.clerk.accounts.dev",
    exp_offset: int = 3600,
    extra: dict | None = None,
) -> str:
    now = int(time.time())
    payload = {
        "sub": sub,
        "iss": iss,
        "iat": now,
        "exp": now + exp_offset,
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, private_key, algorithm="RS256", headers={"kid": "test-kid"})


def _build_middleware_with_pubkey(
    settings: Settings, public_key
) -> AuthMiddleware:
    """PyJWKClient.get_signing_key_from_jwt를 mock해 네트워크 없이 검증."""
    mw = AuthMiddleware(app=lambda *a, **k: None, settings=settings)
    fake_signing_key = MagicMock()
    fake_signing_key.key = public_key
    mw._jwk_client = MagicMock()
    mw._jwk_client.get_signing_key_from_jwt.return_value = fake_signing_key
    return mw


def test_verify_token_valid(rsa_keypair, settings_phase2):
    """정상 발급된 토큰 → sub claim 반환."""
    token = _make_token(rsa_keypair)
    mw = _build_middleware_with_pubkey(settings_phase2, rsa_keypair.public_key())
    assert mw._verify_token(token) == "user_abc123"


def test_verify_token_expired(rsa_keypair, settings_phase2):
    """exp 지난 토큰 → None."""
    token = _make_token(rsa_keypair, exp_offset=-60)
    mw = _build_middleware_with_pubkey(settings_phase2, rsa_keypair.public_key())
    assert mw._verify_token(token) is None


def test_verify_token_wrong_issuer(rsa_keypair, settings_phase2):
    """iss claim이 settings.clerk_issuer와 다르면 None."""
    token = _make_token(rsa_keypair, iss="https://attacker.example.com")
    mw = _build_middleware_with_pubkey(settings_phase2, rsa_keypair.public_key())
    assert mw._verify_token(token) is None


def test_verify_token_wrong_signature(rsa_keypair, settings_phase2):
    """다른 키로 서명한 토큰 → None (서명 검증 실패)."""
    other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    token = _make_token(other_key)
    # JWKS는 원래 keypair 공개키를 반환하므로 검증 시 서명 불일치
    mw = _build_middleware_with_pubkey(settings_phase2, rsa_keypair.public_key())
    assert mw._verify_token(token) is None


def test_verify_token_missing_required_claim(rsa_keypair, settings_phase2):
    """sub claim 없는 토큰 → require=[sub] 위반으로 None."""
    now = int(time.time())
    payload = {
        "iss": "https://example.clerk.accounts.dev",
        "iat": now,
        "exp": now + 3600,
    }
    token = jwt.encode(
        payload, rsa_keypair, algorithm="RS256", headers={"kid": "test-kid"}
    )
    mw = _build_middleware_with_pubkey(settings_phase2, rsa_keypair.public_key())
    assert mw._verify_token(token) is None


def test_verify_token_no_jwks_url():
    """clerk_jwks_url 미설정 → JWKS 클라이언트 생성 시도조차 안 하고 None."""
    settings = Settings(
        openai_api_key="sk-test",
        auth_enabled=True,
        clerk_jwks_url="",
        clerk_issuer="https://example.clerk.accounts.dev",
    )
    mw = AuthMiddleware(app=lambda *a, **k: None, settings=settings)
    assert mw._verify_token("anything") is None


def test_verify_token_no_issuer():
    """clerk_issuer 미설정 → JWKS URL은 있어도 None (issuer 강제 검증 정책)."""
    settings = Settings(
        openai_api_key="sk-test",
        auth_enabled=True,
        clerk_jwks_url="https://example.clerk.accounts.dev/.well-known/jwks.json",
        clerk_issuer="",
    )
    mw = AuthMiddleware(app=lambda *a, **k: None, settings=settings)
    assert mw._verify_token("anything") is None


def test_verify_token_jwks_lookup_failure(rsa_keypair, settings_phase2):
    """JWKS 조회가 PyJWKClientError를 던지면 None (네트워크 장애 등)."""
    from jwt import PyJWKClientError

    token = _make_token(rsa_keypair)
    mw = AuthMiddleware(app=lambda *a, **k: None, settings=settings_phase2)
    mw._jwk_client = MagicMock()
    mw._jwk_client.get_signing_key_from_jwt.side_effect = PyJWKClientError("boom")
    assert mw._verify_token(token) is None


def test_verify_token_non_string_sub(rsa_keypair, settings_phase2):
    """sub claim이 문자열이 아니면 None."""
    token = _make_token(rsa_keypair, extra={"sub": 12345})
    # PyJWT는 sub 타입을 강제하지 않지만 우리 코드가 isinstance(sub, str)로 거른다.
    # _make_token에서 sub를 다시 덮어쓰기 위해 직접 빌드
    now = int(time.time())
    payload = {
        "sub": 12345,
        "iss": "https://example.clerk.accounts.dev",
        "iat": now,
        "exp": now + 3600,
    }
    token = jwt.encode(
        payload, rsa_keypair, algorithm="RS256", headers={"kid": "test-kid"}
    )
    mw = _build_middleware_with_pubkey(settings_phase2, rsa_keypair.public_key())
    assert mw._verify_token(token) is None
