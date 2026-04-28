"""TASK-019 (ADR-030): 인증 미들웨어.

Origin 분기 정책 (Streamlit 코드 동결과 호환):
- Authorization: Bearer <Clerk JWT>     → Clerk 검증 → user_id = clerk.user_id
- 헤더 없음 + LAN/localhost origin       → user_id = 'admin' 자동 (Streamlit + 로컬 스크립트)
- 헤더 없음 + 외부 origin                → 401

`AUTH_ENABLED=false` (Phase 1 기본) 일 때는 JWT 검증을 건너뛰고
모든 요청에 user_id='admin'을 주입한다 (Clerk 키 없이 백엔드만 가동 가능).
"""
from __future__ import annotations

import ipaddress
from urllib.parse import urlparse

import jwt
from jwt import InvalidTokenError, PyJWKClient, PyJWKClientError
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from apps.config import Settings
from packages.code.logger import get_logger

logger = get_logger(__name__)

ADMIN_USER_ID = "admin"


def _is_lan_host(host: str) -> bool:
    """host가 localhost 또는 RFC1918 사설 대역인지.

    host: "127.0.0.1", "192.168.0.5", "10.0.0.1", "[::1]" 등.
    포트는 미리 분리되어 있다고 가정.
    """
    if not host:
        return False
    if host in ("localhost", "::1", "[::1]"):
        return True
    # IPv6 대괄호 제거
    if host.startswith("[") and host.endswith("]"):
        host = host[1:-1]
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        # 호스트명이 IP가 아니면 LAN으로 보지 않음
        return False
    return ip.is_loopback or ip.is_private


def _origin_host(request: Request) -> str:
    """요청 출처 host 추출. Origin → Referer → 클라이언트 IP 순으로 fallback."""
    origin = request.headers.get("origin") or request.headers.get("referer")
    if origin:
        try:
            parsed = urlparse(origin)
            if parsed.hostname:
                return parsed.hostname
        except Exception:
            pass
    client = request.client
    return client.host if client else ""


class AuthMiddleware(BaseHTTPMiddleware):
    """JWT 검증 + Origin 분기 + user_id 주입.

    request.state.user_id 에 결정된 user_id를 둔다. 다운스트림 라우터·repository는
    이 값을 사용해 자기 데이터만 조회·생성한다.
    """

    EXEMPT_PATHS = {"/health", "/docs", "/redoc", "/openapi.json"}

    def __init__(self, app: ASGIApp, settings: Settings) -> None:
        super().__init__(app)
        self._settings = settings
        # JWKS 클라이언트는 첫 검증 호출에서 lazy 생성 (PyJWKClient 내부에 키 캐시 보유).
        # auth_enabled=false 또는 clerk_jwks_url 미설정 시 None 유지.
        self._jwk_client: PyJWKClient | None = None

    async def dispatch(self, request: Request, call_next) -> Response:
        # health/문서 엔드포인트는 인증 면제 (모니터링 용도)
        if request.url.path in self.EXEMPT_PATHS:
            request.state.user_id = ADMIN_USER_ID
            return await call_next(request)

        # OPTIONS preflight는 CORSMiddleware에 위임 (인증 없이 통과)
        if request.method == "OPTIONS":
            request.state.user_id = ADMIN_USER_ID
            return await call_next(request)

        auth_header = request.headers.get("authorization", "")
        token = ""
        if auth_header.lower().startswith("bearer "):
            token = auth_header[7:].strip()

        # AUTH_ENABLED=false: JWT 검증 건너뛰고 모든 요청 통과 (admin 부여)
        if not self._settings.auth_enabled:
            request.state.user_id = ADMIN_USER_ID
            return await call_next(request)

        # AUTH_ENABLED=true 경로 — 토큰 있으면 Clerk 검증, 없으면 LAN/origin 분기
        if token:
            user_id = self._verify_token(token)
            if not user_id:
                return JSONResponse(
                    status_code=401,
                    content={"detail": "유효하지 않은 인증 토큰"},
                )
            request.state.user_id = user_id
            return await call_next(request)

        # 헤더 없음 — Origin 분기
        host = _origin_host(request)
        if _is_lan_host(host):
            request.state.user_id = ADMIN_USER_ID
            return await call_next(request)

        return JSONResponse(
            status_code=401,
            content={"detail": "로그인이 필요합니다"},
        )

    def _verify_token(self, token: str) -> str | None:
        """Clerk JWT 검증 (RS256, JWKS).

        절차:
        1) 토큰 헤더 `kid`로 JWKS에서 공개키 조회 (PyJWKClient 내부 캐시)
        2) RS256 서명 검증 + `exp`/`nbf`/`iat` 자동 검증
        3) `iss`가 settings.clerk_issuer 와 일치하는지 검증
        4) `sub` claim을 user_id로 반환 (Clerk user_xxx 형태)

        실패 시 None 반환 → 미들웨어가 401. 어떤 단계에서든 예외는 흡수해 누설 차단.
        """
        if not self._settings.clerk_jwks_url or not self._settings.clerk_issuer:
            logger.warning("Clerk JWKS URL 또는 issuer 미설정 — JWT 검증 불가")
            return None

        if self._jwk_client is None:
            # PyJWKClient는 내부에서 응답 캐시 (max_cached_keys 기본 16, lifespan 300s)
            self._jwk_client = PyJWKClient(self._settings.clerk_jwks_url)

        try:
            signing_key = self._jwk_client.get_signing_key_from_jwt(token)
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                issuer=self._settings.clerk_issuer,
                # Clerk 토큰은 audience claim 없이 발급되는 경우가 일반적이라
                # aud 검증은 비활성화 (서명·exp·iss로 충분히 강함)
                options={"verify_aud": False, "require": ["exp", "iat", "sub", "iss"]},
            )
        except PyJWKClientError as exc:
            logger.warning("JWKS 키 조회 실패: %s", exc)
            return None
        except InvalidTokenError as exc:
            # 만료·서명 불일치·issuer 불일치·claim 누락 모두 여기로
            logger.info("JWT 검증 거부: %s", exc)
            return None
        except Exception as exc:  # noqa: BLE001
            logger.exception("JWT 검증 중 예기치 못한 오류: %s", exc)
            return None

        sub = payload.get("sub")
        if not isinstance(sub, str) or not sub:
            logger.info("JWT에 sub claim 없음 또는 비문자열")
            return None
        return sub


def get_request_user_id(request: Request) -> str:
    """라우터 의존성 — 미들웨어가 주입한 user_id 반환. fallback admin."""
    return getattr(request.state, "user_id", ADMIN_USER_ID)
