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
        # Clerk JWT 검증기는 Phase 2에서 lazy import. 현재는 stub.
        self._verifier = None

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
        """Clerk JWT 검증. Phase 2에서 PyJWT + JWKS로 구현.

        Phase 1에선 stub: 토큰이 들어오면 Authorization 헤더 형식만 통과시키고
        실제 검증은 미수행 (AUTH_ENABLED=true이면서 키 미발급 환경에서 401 회피).
        Phase 2에서 본격 검증으로 전환할 때 이 함수만 교체.
        """
        if not self._settings.clerk_jwks_url:
            logger.warning("Clerk JWKS URL 미설정 — JWT 검증 stub 모드")
            return None
        # TODO Phase 2: PyJWT + JWKS로 sub claim 추출, exp/aud 검증
        logger.warning("Clerk JWT 검증 미구현 (Phase 2) — 토큰 거부")
        return None


def get_request_user_id(request: Request) -> str:
    """라우터 의존성 — 미들웨어가 주입한 user_id 반환. fallback admin."""
    return getattr(request.state, "user_id", ADMIN_USER_ID)
