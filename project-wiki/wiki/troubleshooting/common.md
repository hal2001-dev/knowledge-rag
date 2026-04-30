# 트러블슈팅 (Troubleshooting)

**상태**: active
**마지막 업데이트**: 2026-04-30
**관련 페이지**: `issues/`, [setup.md](../onboarding/setup.md)

이슈가 해결될 때마다 여기에 누적합니다.
"또 이 에러다" 싶으면 여기서 먼저 찾아보세요.

---

## 형식

```markdown
### [에러명 또는 증상]
**발생 상황**: 언제 발생하는지
**에러 메시지**: (있다면)
**원인**: 왜 발생하는지
**해결**: 어떻게 고치는지
**관련 이슈**: `issues/resolved/ISSUE-NNN.md`
```

---

## 환경 셋업

### ModuleNotFoundError: No module named 'faiss'
**발생 상황**: `import faiss` 실행 시
**원인**: faiss-cpu 미설치 또는 가상환경 미활성화
**해결**:
```bash
pip install faiss-cpu
# GPU 환경이면
pip install faiss-gpu
```

### OpenAI API 인증 오류 (AuthenticationError)
**발생 상황**: 임베딩 또는 LLM 호출 시
**원인**: `.env` 파일에 API 키 미설정 또는 키 만료
**해결**:
```bash
# .env 파일 확인
cat .env | grep OPENAI_API_KEY
# 키 재발급: https://platform.openai.com/api-keys
```

---

## 인덱싱 (Ingestion)

### PDF 파싱 결과가 빈/매우 작은 청크 수
**발생 상황**: 업로드 성공 후 `chunk_count=0` 또는 페이지 수 대비 비정상적으로 적음
**정정 (2026-04-23)**: "스캔 PDF = OCR 미지원"이라는 이전 기록은 **부정확**했음. Docling의 `do_ocr=True`가 기본값이라 스캔 PDF도 자동 EasyOCR로 처리됨. 자세한 플로우는 [spec.md](../data/spec.md#pdf-처리-프로세스-end-to-end) 참고
**실제 원인들**:
- **보안 PDF** (암호·편집 제한): Docling이 페이지 접근 불가 → 텍스트·OCR 모두 실패
- **손상된 PDF**: 파일 구조 깨짐
- **폰트 임베딩 없는 비정상 PDF**: 일부 페이지만 빈 문자열
- **매우 흐린 스캔·손글씨**: OCR 실행은 되나 결과가 대부분 빈 문자열·노이즈
- **보안 워터마크 전면 오버레이**: OCR이 텍스트 영역을 제대로 못 뽑음
**해결**:
- 원본 PDF를 다른 뷰어(Adobe Reader 등)로 열어 텍스트 선택이 되는지 먼저 확인
- 보안 제한이 있으면 제한 제거 후 재업로드
- OCR 품질 문제면 더 고해상도 스캔 또는 이미지 전처리(콘트라스트 조정) 후 재시도
- 서버 로그에서 Docling이 `OcrModel`을 호출했는지 확인 (OCR 경로 진입 여부)

### FAISS 인덱스 저장 후 로드 시 오류
**발생 상황**: `faiss.read_index()` 실행 시
**원인**: 인덱스 파일만 저장하고 docstore pickle 미저장
**해결**:
```python
# 저장 시 반드시 함께 저장
faiss.write_index(index, "index.faiss")
with open("docstore.pkl", "wb") as f:
    pickle.dump(docstore, f)

# 로드 시
index = faiss.read_index("index.faiss")
with open("docstore.pkl", "rb") as f:
    docstore = pickle.load(f)
```
**참고**: [patterns.md](../reviews/patterns.md)

---

## 검색 (Retrieval)

### 검색 결과가 항상 같은 문서만 나옴
**발생 상황**: 다양한 질문에도 동일 결과 반환
**원인**: 청크 크기가 너무 크거나 임베딩 품질 문제
**해결**: chunk_size 줄이거나 임베딩 모델 변경 → [evaluation.md](../features/evaluation.md) 실험 기록 참고

---

## LLM 호출

### RateLimitError
**발생 상황**: 짧은 시간에 많은 요청 시
**해결**:
```python
import time
time.sleep(1)  # 요청 간 딜레이 추가
# 또는 배치 크기 줄이기
```

---

---

## UI (Streamlit)

### 후속 질문 배지 두 번째 이후 클릭 무반응 (미해결 — ISSUE-002)
**상태**: 🛑 **open, 보류** — 3회 수정(0.14.1/0.14.2/0.14.3) 시도했으나 증상 지속. 모바일 특정 이슈로 의심. 상세는 [ISSUE-002](../issues/open/ISSUE-002-suggestion-badge-click-unresponsive.md)
**발생 상황**: 답변 아래 suggestions 배지 #1 클릭은 정상이나, 같은 답변의 다른 배지 또는 empty state의 예시 질문 선택 후 이어지는 배지 클릭이 무반응 (모바일 재현 확인)
**시도했던 수정 (모두 오진, 증상 지속)**:
- v1 (0.14.1): 명시적 `st.rerun()` 제거
- v2 (0.14.2): 배지 렌더를 `st.chat_message` 블록 바깥으로 이동
- v3 (0.14.3): 라이브·히스토리 key 접두사를 `msg_{msg_idx}`로 통일
- 위 3개 수정은 Streamlit 모범 사례에 부합해 유지하되 원인은 아니었음
**가능성 높은 남은 원인**:
- 🥇 모바일 Streamlit WebSocket 이벤트 누락 (ISSUE-001과 같은 계열) — HTTPS 배포로 해결 가능성
- 🥈 자동 스크롤 누락으로 사용자 오인 (답변이 화면 밖에 렌더)
- 🥉 Streamlit 1.56.0 특정 버그
**현재 회피**: 데스크톱(PC) 브라우저에서 채팅 사용. 모바일에서는 `st.chat_input`으로 수동 입력
**재개 조건**: "인증·공개배포 묶음"의 일부로 ISSUE-001 + 관리자 UI 2단계 + HTTPS와 함께 처리
**참고**: changelog [0.14.1]·[0.14.2]·[0.14.3], ADR-019 회고 섹션

### 모바일에서 파일 선택 후 선택된 파일이 표시되지 않음
**발생 상황**: 모바일(iOS Safari / Android Chrome 등)에서 `http://<LAN|WAN IP>:8501` 접속, "파일 선택" → 피커에서 파일 선택 후 돌아왔을 때 위젯이 비어 보이고 업로드가 안 됨
**원인(가설)**:
- HTTP 평문 + WebSocket mixed-content로 모바일이 업로드 XHR을 조용히 드롭
- 또는 Streamlit 1.56.0의 모바일 회귀
- 또는 모바일 파일 피커의 MIME 정책으로 "선택한 듯 보이나 실제로는 전달 안 됨"
**임시 회피**: PC에서 업로드, 모바일은 `/query`만 사용
**근본 해결 방향**: HTTPS 리버스 프록시 배포 후 재확인
**관련 이슈**: [ISSUE-001-mobile-file-uploader-no-preview.md](../issues/open/ISSUE-001-mobile-file-uploader-no-preview.md)

### Qdrant collection drop 후 잡이 매 retry마다 404로 실패

**발생 상황**: `처음부터 새로` 정리 목적으로 Qdrant collection을 drop(또는 재생성)한 직후, 큐에 새로 enqueue한 잡이 매 retry마다 같은 위치에서 실패. 워커는 살아 있고 다른 에러는 없는데 collection이 "없다"고 응답
**에러 메시지**:
```
qdrant_client.http.exceptions.UnexpectedResponse: Unexpected Response: 404 (Not Found)
b'{"status":{"error":"Not found: Collection `documents` doesn\'t exist!"}}'
```
**원인**:
- 색인 워커(`apps.indexer_worker`)가 부팅 시점에 한 번만 `_ensure_collection()`을 실행하고 그 후엔 collection 존재를 가정해 raw `client.upsert()`를 호출 (hybrid 모드 경로)
- 외부에서 collection을 drop해도 워커는 캐시된 가정 그대로 → 매 잡 처리에서 404
- retry 3회 모두 같은 위치에서 실패 후 영구 `failed`
**해결**:
1. 워커 재기동 (init에서 `_ensure_collection()` 재호출 → collection 재생성)
   ```bash
   pkill -f "apps.indexer_worker"
   sleep 3
   nohup .venv/bin/python -m apps.indexer_worker > /tmp/indexer.log 2>&1 &
   ```
2. retry 소진된 잡이나 stuck `in_progress` 잡은 SQL로 reset
   ```sql
   UPDATE ingest_jobs
   SET status='pending', retry_count=0, error=NULL,
       started_at=NULL, finished_at=NULL
   WHERE id IN (...);
   ```
3. 새 워커가 즉시 polling cycle에서 잡을 다시 claim
**재발 방지 / 운영 절차**:
- **인덱싱 데이터 정리 절차에 항상 워커 재기동 포함**:
  1. (선택) 잡 큐 enqueue 중지
  2. PostgreSQL `TRUNCATE documents, ingest_jobs, conversations, messages CASCADE`
  3. Qdrant collection drop
  4. `data/uploads/*`, `data/markdown/*`, `data/eval_runs/*` 정리
  5. **워커 재기동** ← 이 단계 누락 시 본 에러 발생
  6. (선택) FastAPI uvicorn 재기동 (스키마 변경 동반 시)
**관련**: ADR-028 "stale `in_progress` 잡 자동 회수 미구현" — 본 케이스도 같은 카테고리. housekeeping 잡으로 자동 회수 도입 시 수동 reset 불필요
**상황 발견**: 2026-04-26 TASK-019 Phase 1 진행 중 fresh start 정리 후 재인덱싱 시도. 잡 #1이 retry 0→1→2→3 모두 동일 404로 실패. 워커 재기동 + reset SQL 1회로 복구

### `/ingest` 업로드 시 타임아웃 발생
**발생 상황**: Streamlit UI에서 문서 업로드 후 처리 대기 중 연결 끊김
**에러 메시지**: `requests.exceptions.ReadTimeout`
**원인 1**: Docling 첫 실행 시 AI 모델(TableFormer 등) 다운로드로 수 분 소요
**원인 2**: 대용량 PDF 파싱 시간이 기본 타임아웃(120초) 초과
**해결**: `ui/app.py` 34번째 줄 `timeout` 값을 600으로 변경
```python
# 변경 전
timeout=120
# 변경 후
timeout=600
```
**참고**: Docling 모델은 최초 1회 다운로드 후 캐시됨. 이후 실행은 빠름.

### bulk 인덱싱 중 macOS freeze (워커 동시 기동)
**발생 상황**: `bulk_ingest --via-queue`로 큰 PDF 다수 enqueue 후, `apps.indexer_worker`를 두 개 이상 띄운 상태에서 시스템 응답 불가
**증상**: 처음 작은 PDF 몇 건은 정상, 80MB+ PDF 만나는 시점에 합산 RSS 14~16GB → swap 폭주 → 강제 종료 외 회복 불가
**원인**: 워커 동시 기동 가드 부재. 단일 잡당 RSS 5~12GB 사용하므로 워커 2개면 합산이 OS 임계 초과 (ISSUE-003 후속 진단)
**해결**:
```bash
# 띄우기 전 확인 — 비어 있어야 함
pgrep -fl "apps.indexer_worker"
# 살아있는 워커 발견 시 graceful 종료
pkill -TERM -f "apps.indexer_worker"
# 새 워커 1개만 띄움
.venv/bin/python -m apps.indexer_worker
```
**재발 방지**: 운영자 직접 1개 보장. 가드(pidfile/Postgres advisory lock) 도입은 후속 P0 작업
**관련**: [ISSUE-003 후속 노트](../issues/resolved/ISSUE-003-ingest-memory-spike-system-freeze.md), [ISSUE-004](../issues/open/ISSUE-004-docling-parse-longtail.md)

### stale `in_progress` 잡 수동 reset
**발생 상황**: 워커를 SIGKILL로 강제 종료한 직후 잡이 `status='in_progress'`로 영원히 잠김. 다른 워커도 안 잡음(`FOR UPDATE SKIP LOCKED`)
**원인**: `apps.indexer_worker._process_job` 도중 프로세스 죽으면 `mark_done`/`mark_failed`가 실행되지 않아 status·started_at만 남음
**해결**: SQL로 `pending`으로 reset (워커 폴링 주기에서 자동 재claim)
```bash
.venv/bin/python -c "
from dotenv import load_dotenv; load_dotenv()
from sqlalchemy import create_engine, text
import os
e = create_engine(os.environ['POSTGRES_URL'])
with e.begin() as c:
    rows = c.execute(text('''
        UPDATE ingest_jobs
        SET status='pending', retry_count=0, error=NULL, started_at=NULL, finished_at=NULL
        WHERE status='in_progress' AND started_at < now() - interval '10 minutes'
        RETURNING id, title
    ''')).fetchall()
    for r in rows: print('reset:', r)
"
```
**참고**: 이미 hash 중복인 잡은 워커가 즉시 done 처리. retry_count=4(영구 실패)도 같은 패턴으로 일괄 reset 가능 (`status IN ('failed','in_progress')`)
**관련**: ADR-028 후속, [ISSUE-003 후속 노트](../issues/resolved/ISSUE-003-ingest-memory-spike-system-freeze.md)

---

## NextJS 사용자 UI

### 도서관·채팅 화면이 비어 있고 `/api/*` 호출이 0건 (HTTP LAN host 접속)
**발생 상황**: `http://macstudio:3000/library` 같은 HTTP + LAN hostname으로 접속할 때. localhost·127.0.0.1로는 정상.
**증상**: 도서관 "총 0/0개 문서", 사이드바 "로딩…" 영구. DevTools Network에 `/library → 307 → clerk handshake → 307 → /library?__clerk_handshake=... → 307` 패턴 무한 반복. `/api/documents` 호출 자체가 발생 안 함.
**원인**: Clerk dev instance handshake 응답 쿠키가 `Secure; SameSite=None`. 브라우저는 HTTPS 컨텍스트에서만 Secure 쿠키 저장(localhost는 예외). LAN hostname은 예외 아님 → 쿠키 미저장 → 핸드셰이크 무한 루프 → ClerkProvider settle 안 됨 → React Query fetch 시작 못함.
**해결**: `web/.env.local`에 `NEXT_PUBLIC_AUTH_ENABLED=false` 설정 후 `pnpm dev` 재시작. ClerkProvider/UserButton/useAuth 호출이 모두 우회됨 (Phase 1 토글 — `web/lib/auth-flag.ts` 단일 진실).
**관련 이슈**: [ISSUE-009](../issues/resolved/ISSUE-009-clerk-handshake-loop-http-lan.md), ADR-030

### NextJS dev — `Blocked cross-origin request to Next.js dev resource` 경고
**발생 상황**: LAN hostname(macstudio 등)·Tailscale IP로 dev 서버 접속 시 webpack HMR 실패.
**원인**: NextJS 16 dev 서버는 기본적으로 외부 origin을 차단(localhost·127.0.0.1만 허용).
**해결**: `web/next.config.ts`의 `allowedDevOrigins`에 hostname 또는 IP 추가 후 dev 서버 재시작.
```ts
allowedDevOrigins: ["192.168.0.72", "100.78.13.90", "macstudio"],
```

---

> 새 에러 해결 시 여기에 추가: "troubleshooting에 추가해줘"
