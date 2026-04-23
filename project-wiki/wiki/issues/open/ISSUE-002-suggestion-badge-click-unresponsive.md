---
name: ISSUE-002 후속 질문 배지 두 번째 이후 클릭 무반응
description: 답변 후 suggestions 배지를 두 번째로 이상 연속 클릭하면 재질의가 트리거되지 않음 (특히 모바일에서 재현)
type: issue
---

# ISSUE-002: 후속 질문 배지 두 번째 이후 클릭 무반응

**상태**: open · **🛑 보류 — 모바일 특정 이슈 의심, 인증·공개배포 묶음과 함께 처리**
**발생일**: 2026-04-22
**해결일**: -
**관련 기능**: [admin_ui.md](../../features/admin_ui.md) · `ui/app.py` 채팅 탭의 `_render_suggestions()`
**관련 변경 이력**: changelog [0.14.1]·[0.14.2]·[0.14.3] — 3회 오진·수정 시도에도 증상 지속

---

## 증상

1. 빈 채팅에서 예시 질문 "딥러닝의 기본 개념은 무엇인가요" (empty state 카드) 클릭 → 답변 정상
2. 답변 하단의 suggestions 배지 중 하나를 클릭 → **반응 없음** (재질의 트리거 안 됨)
3. 또는: 답변 A 생성 후 배지 #1 클릭 → 답변 B 생성 → 답변 A의 다른 배지 #2 클릭 → 반응 없음

시크릿 탭·하드 리프레시로도 재현. Streamlit 서버 재시작 후에도 재현.

## 테스트 환경

사용자 보고 시점: **모바일 브라우저에서 재현 확인**. 데스크톱 검증은 아직 미수행.

- [ ] 데스크톱 Chrome
- [ ] 데스크톱 Safari
- [ ] 데스크톱 Firefox
- [ ] iOS Safari
- [ ] iOS Chrome
- [ ] Android Chrome
- [ ] 기타: ___

## 3회 오진·수정 기록 (증상 지속)

| 버전 | 가설 | 조치 | 결과 |
|---|---|---|---|
| 0.14.1 | 명시적 `st.rerun()` 호출이 자동 rerun과 중복되어 state 꼬임 | `_render_suggestions`·empty state 핸들러에서 `st.rerun()` 제거 | 증상 지속 |
| 0.14.2 | `st.button`이 `st.chat_message` 컨테이너 내부에서 호출되어 widget state 경쟁 | 배지 렌더를 `with st.chat_message(...)` 블록 바깥으로 이동 | 증상 지속 |
| 0.14.3 | 라이브 렌더 key(`live_{N}_sug_*`)와 히스토리 렌더 key(`hist_{M}_sug_*`) 불일치로 widget state 분리 | 두 경로 key 접두사를 `msg_{msg_idx}`로 통일 | 증상 지속 |

위 3개 수정은 모두 Streamlit 모범 사례에 부합하므로 **되돌리지 않음**. 다만 근본 원인은 아니었음을 명확히 기록.

## 남은 원인 가설

### 🥇 가설 A — 모바일 특정 Streamlit WebSocket 이벤트 누락
- ISSUE-001(모바일 파일 업로더)과 **같은 계열**의 문제일 가능성. Streamlit은 WebSocket으로 widget 이벤트를 서버에 전달하는데, 모바일 브라우저(특히 iOS Safari)에서 mixed-content·백그라운드 탭 정책 때문에 이벤트가 누락될 수 있음
- 데스크톱에서 재현되지 않으면 이 가설로 확정. **ISSUE-001과 묶어 HTTPS 배포(관리자 UI 2단계) 시점에 재검증**

### 🥈 가설 B — 자동 스크롤 누락으로 사용자 오인
- 배지 클릭이 실제로 질의를 트리거하고 새 답변이 메시지 리스트에 추가되었으나, 모바일에서 **화면 스크롤이 자동으로 최하단으로 내려가지 않아** 사용자가 "반응 없음"으로 오인
- 검증: 모바일에서 배지 클릭 후 **화면을 위·아래로 수동 스크롤**해 새 사용자 메시지·답변이 어딘가에 추가됐는지 확인

### 🥉 가설 C — Streamlit 특정 버그 (버전 1.56.0)
- watchdog 미설치 상태에서 polling 기반 file watcher 때문에 일부 rerun에서 state가 직전 버전에 머무르는 경우
- 검증: watchdog 설치 (`pip install watchdog`) 후 재시도

## 진단 체크리스트 (재개 시 수행)

1. **데스크톱에서 동일 시나리오 재현 여부 확인** — `http://localhost:8501` 시크릿 탭
   - 데스크톱 OK → **가설 A 확정** (모바일 특정)
   - 데스크톱 실패 → 가설 C 검토, 추가 진단 필요
2. **모바일에서 화면 스크롤** 후 새 메시지 존재 여부 확인 → 가설 B 검증
3. 모바일 Safari Mac 원격 디버깅 / Chrome `chrome://inspect`로 **Network 탭 WebSocket 프레임** 확인 — 배지 클릭 시 `widget_event` 메시지가 서버로 전송되는지
4. watchdog 설치 후 재현

## 현재 회피

- **데스크톱(PC) 브라우저에서만 채팅 사용** — 배지 클릭이 정상 동작하면 모바일 한정 문제로 확정 (ISSUE-001과 동일 계열)
- 모바일에서는 `st.chat_input`으로 수동 질의 입력

## 재개 조건

사용자 명시적 지시까지 자동 진행 금지. **"인증·공개배포 묶음"의 일부로 ISSUE-001 + 관리자 UI 2단계 + HTTPS 배포와 함께 처리**. HTTPS 배포 후 같은 증상이 재현되면 별도 조치 필요.

## 관련 페이지 / 이력

- changelog [0.14.1]·[0.14.2]·[0.14.3] — 시도한 수정들
- ADR-019 회고·수정 이력 섹션
- [common.md](../../troubleshooting/common.md) — UI 섹션에 요약 항목
- [ISSUE-001](ISSUE-001-mobile-file-uploader-no-preview.md) — 유사 모바일 Streamlit 이슈, 같은 묶음
- [log.md](../../../log.md) 2026-04-22 항목들
