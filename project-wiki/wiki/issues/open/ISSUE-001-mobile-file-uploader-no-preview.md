---
name: ISSUE-001 모바일 파일 업로더 선택 후 파일명 미표시
description: 모바일 브라우저에서 파일 선택 후 Streamlit file_uploader가 선택된 파일 정보를 표시하지 않음
type: issue
---

# ISSUE-001: 모바일에서 파일 업로드 선택 시 선택된 파일이 표시되지 않음

**상태**: open · **🛑 보류 — "인증·공개배포 묶음"의 일부**
**발생일**: 2026-04-22
**해결일**: -
**관련 기능**: `ingestion.md` _(미작성)_, [admin_ui.md](../../features/admin_ui.md) (관리자 UI 2단계에서 동반 해결), [ui/app.py](../../../ui/app.py)
**재개 조건**: 사용자 명시적 지시까지 자동 진행 금지. 2026-04-22 이후 "인증·공개배포 묶음"에 포함 (ISSUE-001 + 관리자 UI 2단계 + HTTPS + API 키/OAuth). 개인·내부 시스템 단계라 일괄 보류.
**향후 착수 시 범위**: 원인 확정(진단 로그 수집 또는 ngrok HTTPS 테스트) → HTTPS 리버스 프록시 배포 → 관리자 UI 2단계(`/admin` 분리 + `ADMIN_PASSWORD`) 묶어 처리

---

## 증상

- 모바일 브라우저(iOS Safari / Android Chrome 등)에서 `http://<LAN 또는 WAN IP>:8501`로 접속한 뒤
- 사이드바의 "파일 선택" 영역을 탭하면 모바일 파일 피커가 열리고, 파일을 선택해 피커를 닫음
- **기대**: Streamlit `file_uploader` 위젯에 파일명·크기·× 제거 버튼이 표시됨. 추가로 [ui/app.py](../../../ui/app.py)의 `st.caption("선택됨: ...")`도 출력
- **실제**: 위젯이 선택된 파일을 전혀 표시하지 않고 비어 있는 것처럼 보임. "업로드 & 인덱싱" 버튼을 눌러도 "파일을 선택하세요" 에러가 뜰 수 있음(= Streamlit이 파일을 수신하지 못함)

데스크톱에서는 동일 코드로 정상 표시됨.

## 재현 환경

- [ ] iOS Safari
- [ ] iOS Chrome
- [ ] Android Chrome
- [ ] 기타: ___
- 접속 URL 형태: `http://192.168.x.x:8501` (LAN) / `http://203.x.x.x:8501` (WAN)

_(재현 시 체크 부탁)_

## 원인 가설

관련 코드는 [ui/app.py:17-31](../../../ui/app.py#L17-L31), [.streamlit/config.toml](../../../.streamlit/config.toml).

1. **Streamlit WebSocket fileUploader upload 실패** — HTTP 평문 + LAN IP 접속 시 모바일 브라우저의 mixed-content/cookie 정책으로 업로드 XHR이 조용히 드롭되는 사례 존재. 위젯은 첨부를 받았지만 서버 측 `session_state`에 반영되지 못함
2. **XSRF/CORS 보호** — 현재 `enableXsrfProtection=false`, `enableCORS=false`로 개발망에서 비활성했지만, WebSocket 토큰 교환이 별도 경로라 모바일에서만 실패할 가능성
3. **`type=None`으로 화이트리스트를 제거**한 이후에도 모바일 파일 피커가 MIME 기반으로 일부 파일을 "보이긴 하나 선택 불가" 상태로 넘기는 경우 — 이 경우 위젯이 파일 객체를 받지 못해 표시하지 않음
4. **Streamlit 버전(1.56.0) 모바일 회귀 버그** 가능성 — 일부 공개 이슈에 유사 사례

## 현재 임시 회피

- 데스크톱 브라우저 또는 같은 Wi-Fi의 PC에서 업로드 후, 모바일에서는 `/query`만 사용
- ngrok 등으로 HTTPS 터널을 걸어 접속해 보기 (mixed-content 해소 여부 확인)

## 해결 방향 후보 (우선순위 순)

1. **진단 정보 수집** — 재현 시 브라우저 종류/버전, 파일 확장자, 크기, 개발자도구(모바일 Safari는 Mac Safari 원격 디버깅 / Chrome은 `chrome://inspect`) 콘솔·Network 로그 확인. WebSocket 메시지에 FileUploadResponse가 오는지 점검
2. **HTTPS 강제** — 리버스 프록시(Nginx/Caddy) + Let's Encrypt로 `https://` 접속 가능하게 한 뒤 증상이 사라지는지 검증. 가장 흔한 원인 가설 (1) 해결
3. **API 직업로드 폴백** — Streamlit을 우회하고 모바일 전용 간이 HTML 업로드 페이지(FastAPI에서 직접 multipart 수용)를 추가해 증상 재현이 환경/Streamlit 때문인지 분리
4. **파일을 base64로 텍스트 input에 붙여 업로드하는 워크어라운드** — 가장 hacky. 마지막 수단

## 재발 방지 / 영향

- 운영 단계에서 HTTPS + 공식 도메인으로 배포될 예정이라 L2 조치로 근본 해결될 가능성 높음
- 현재는 개발 환경 한정 문제. 일반 사용자 경로는 PC → `/query`이므로 블로커 아님

## 관련 페이지 / 이력

- [common.md](../../troubleshooting/common.md) 에 단축 항목 등록 필요
- [security.md](../../../security.md) 의 "Streamlit HTTP 평문" 알려진 이슈와 연결됨
- [log.md](../../../log.md) 2026-04-22 항목에 링크
