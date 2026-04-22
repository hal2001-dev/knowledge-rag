# 관리자 UI (Admin UI)

**상태**: active (1단계 구현 완료 2026-04-22)
**마지막 업데이트**: 2026-04-22
**관련 페이지**: [schema.md](../data/schema.md), [endpoints.md](../api/endpoints.md), [decisions.md](../architecture/decisions.md) (ADR-017 예정), [evaluation.md](evaluation.md)

---

## 목적

운영·튜닝·디버깅에 필요한 가시성을 한 화면에서 제공. 현재는 `.env`, Qdrant 대시보드, `data/eval_runs/*.json`, LangSmith가 흩어져 있어 **"지금 이 서버가 무엇으로 돌고 어떤 상태인지"** 한눈에 파악 불가.

## 단계 구분 (ADR-017 예정)

| 단계 | 형태 | 인증 | 배포 요건 | 구현 시점 |
|------|------|------|----------|----------|
| **1단계** | 현 Streamlit 앱 내 탭 추가 | 없음 (LAN 전용) | 변동 없음 | ✅ TASK-005 완료 (2026-04-22, ADR-017) |
| 2단계 | `ui/pages/admin.py` 분리 + `ADMIN_PASSWORD` 게이트 | Basic/패스워드 | HTTPS (ISSUE-001 해결 동반) | HTTPS 배포 시점 |
| 3단계 | FastAPI + Jinja2 또는 React 별도 대시보드 | API Key | 규모 확장 시 | 장기 |

---

## 1단계 기능 명세 (TASK-005 범위)

Streamlit `st.tabs(["채팅", "문서", "대화", "시스템", "평가"])`로 5개 탭 구성. **모든 탭은 읽기·목록·삭제 수준**. 서버 재시작이 필요한 설정 변경(`.env` 수정)은 제공하지 않는다.

### 탭 1 — 채팅
기존 기능 그대로 이전.

- 채팅 히스토리 (`st.session_state["messages"]`)
- `/query` 호출 (POST body: `{question, session_id}`)
- 응답에서 `answer`/`sources`/`latency_ms` 표시
- "대화 초기화" 버튼 → `session_state` 리셋
- 현재 `session_id` 뱃지 표시 (UUID 앞 8자)

**상태 분리**: 탭 전환으로 `messages`·`session_id`가 유실되지 않도록 `st.session_state`에 명시적 키 사용.

### 탭 2 — 문서
기존 사이드바의 문서 관리를 여기로 이전.

**기능**
- 상단: 업로드 위젯 (파일, 제목, 출처) → `POST /ingest`. 409 응답 시 기존 doc_id 경고
- 중단: 목록 테이블 — `GET /documents` 결과를 표로 (doc_id 앞 8자 / title / file_type / chunk_count / has_tables / has_images / indexed_at / status)
- 각 행: **"청크 미리보기"** 버튼 + "삭제" 버튼
- 하단(선택 시): **청크 미리보기 패널**
  - Qdrant에서 `metadata.doc_id==선택_id`인 포인트 상위 5~10개를 scroll
  - 컬럼: `chunk_index` / `heading_path` (`>`으로 이어붙임) / `page` / `content_type` / content 앞 200자

**신규 API/헬퍼 필요**
- `QdrantDocumentStore.scroll_by_doc_id(doc_id, limit=10)` — Qdrant payload filter scroll
- 백엔드에 `GET /documents/{doc_id}/chunks?limit=10` 엔드포인트 (UI에서 직접 Qdrant 치지 않도록 권장)

### 탭 3 — 대화
`/conversations` CRUD를 UI로.

**기능**
- 목록: `GET /conversations` — session_id 앞 8자 / title / created_at / updated_at / 메시지 수(2·4·6턴 등). 최근 업데이트 순 정렬
- 필터: "빈 세션 숨기기", "최근 7일", "전체"
- 선택 시: `GET /conversations/{id}`의 `messages` 배열을 채팅 형태로 렌더 (`user`/`assistant` 말풍선 + `created_at`)
- 각 세션 행: "삭제" 버튼 → `DELETE /conversations/{id}` (확인 다이얼로그)
- 일괄 정리: "메시지 0개 세션 모두 삭제" 버튼 (안전 보호로 N개 확인)

### 탭 4 — 시스템
**읽기 전용 설정·상태 카드**. 수정 버튼 없음, 변경 안내만.

| 카드 | 출력 |
|------|------|
| Reranker | `reranker_backend` + `reranker_model_name or "기본"`. 색깔 뱃지 (`bge-m3` / `flashrank`) |
| LLM | `llm_backend:llm_model` (예: `openai:gpt-4o-mini`), `base_url`, `temperature` |
| Embedding | `embedding_backend` / 모델 / 차원. Qdrant 컬렉션 차원과 일치 여부 체크 마크 |
| Qdrant | 컬렉션명, 포인트 수, dim, distance, status — `QdrantClient.get_collection()` |
| PostgreSQL | `documents` 행 수, `conversations`·`messages` 행 수 (쿼리 기반) |
| LangSmith | 활성/비활성, 프로젝트명, 대시보드 링크 버튼 |
| Health | `/health` 200 여부, 서버 PID, 가동 시간(`lifespan` 시작 시각 저장 필요) |

**"설정 변경하려면 `.env` 편집 후 `uvicorn` 재시작하세요"** 고정 메시지 하단 표시.

### 탭 5 — 평가
TASK-004에서 구축한 벤치 결과를 시각화.

**기능**
- `data/eval_runs/`에서 최신 `retrieval_*.json`과 `answers_*.json`을 각각 1개 로드
- 최신 지표 카드 6개: Hit@3 / Precision@3 / Recall@3 / MRR / faithfulness / answer_relevancy
- 히스토리 테이블 (최근 5~10개 실행): 타임스탬프 / backend 조합 / 주요 지표. 타임스탬프 클릭 시 per_query 상세 펼침
- "지금 실행" 버튼은 **1단계에서 제외** (장시간 블로킹, 비용 발생). CLI 사용법만 안내
  ```
  python scripts/bench_retrieval.py --backend bge-m3
  python scripts/bench_answers.py
  ```

---

## 세션 상태 설계 (Streamlit)

탭 간 상태 유지가 안정적이려면 다음 키를 명시적으로 쓴다:

```python
st.session_state.setdefault("messages", [])             # 채팅 로그
st.session_state.setdefault("session_id", None)         # 현재 RAG 세션
st.session_state.setdefault("selected_doc_id", None)    # 문서 탭에서 선택된 문서
st.session_state.setdefault("selected_session_id", None)# 대화 탭에서 선택된 세션
```

탭 변경은 Streamlit 1.56의 `st.tabs` 기본 동작으로 자동. 탭 내부의 rerun이 다른 탭 상태를 건드리지 않도록 **rerun 영향 범위를 선택 키로만** 국한.

---

## 보안·운영 주의

- **1단계는 인증 없음** — `http://localhost:8501` / LAN IP 접속만 허용. 외부망(`203.x.x.x`) 노출 금지
- Streamlit의 `enableXsrfProtection=false`·`enableCORS=false`가 현재 설정이라 공개망 노출 시 위험 ([security.md](../../security.md))
- 삭제 API가 `data/uploads/*`·`data/markdown/*`을 정리하지 않음 → 관리자 UI에서 삭제해도 디스크에는 남음 (별도 태스크에서 해결)
- 2단계 승격 시:
  - 페이지 분리 (`ui/pages/admin.py`)
  - `ADMIN_PASSWORD` 환경변수 게이트 (`st.text_input(..., type="password")`)
  - Nginx/Caddy + TLS 뒤에 배치
  - ISSUE-001(모바일 업로드) 동반 해결

---

## 의도적으로 1단계에서 제외한 것

| 기능 | 이유 | 대체 수단 |
|------|------|----------|
| 설정 변경 UI (토글 ·드롭다운) | 서버 재시작 필요, 경쟁 상태 위험 | `.env` 편집 + `uvicorn` 재시작 |
| 재인덱싱 트리거 버튼 | 장시간 블로킹(분 단위), 실패 복구 로직 필요 | `python pipeline/rebuild_index.py` |
| 벤치 실행 버튼 | API 비용 발생, 블로킹 | `python scripts/bench_{retrieval,answers}.py` |
| 사용자 관리 | 프로젝트 범위 아님 | 없음 |
| API 키 회전 UI | 보안 민감, 별도 키 관리 체계 필요 | `.env` 수정 + revoke/재발급 ([security.md](../../security.md)) |
| 청크 검색 디버거 (질의 → 20개 후보 전부 점수 표시) | 유용하나 1단계 범위 초과 | Qdrant 대시보드 `http://localhost:6333/dashboard` |
| LangSmith 트레이스 임베드 | 외부 서비스 iframe 제약 | LangSmith 프로젝트 링크 버튼 제공 |

---

## 완료 기준 (TASK-005)

1. 좌측 탭 5개가 정상 전환, 탭 전환으로 채팅 `session_id`·`messages` 유실 없음
2. **문서**: 업로드/삭제/청크 미리보기(5개 이상) 동작
3. **대화**: 목록·메시지 뷰·삭제 동작, 빈 세션 일괄 정리 동작
4. **시스템**: 7개 카드가 현재 설정·상태를 올바르게 반영
5. **평가**: 최신 1회 결과 + 히스토리 5개 이상 표시
6. 스크린샷 2~3장이 본 문서 또는 별도 섹션에 첨부

---

## 2단계·3단계 예정 기능 (참고)

**2단계 (HTTPS 배포 + 관리자 분리)**:
- `ui/pages/admin.py` 파일 분리 (Streamlit multipage)
- `ADMIN_PASSWORD` 게이트
- 재인덱싱·벤치 실행을 background task로 (실행 상태를 DB에 기록)
- ISSUE-001(모바일 업로드) 동반 해결

**3단계 (전용 대시보드)**:
- FastAPI + Jinja2 또는 React
- 청크 검색 디버거 (Qdrant 필터 쿼리 빌더)
- 벤치 결과 시계열 차트 (Plotly)
- 문서별 LangSmith run 링크 자동 생성
- 설정 토글 UI (재시작 예약 시스템 포함)
- 사용량/비용 대시보드

이후 요구에 따라 단계적으로 승격. 각 단계는 별도 태스크·ADR로 관리.
