# 로드맵

**상태**: active
**마지막 업데이트**: 2026-04-21
**관련 페이지**: [[overview.md]], [[requirements/features.md]]

---

## 마일스톤

| 마일스톤 | 목표일 | 상태 | 내용 |
|----------|--------|------|------|
| M1: 기반 구축 | 2026-04-19 | `done` | Docling 파싱, Qdrant 인덱싱, PostgreSQL 메타데이터 |
| M2: 검색 동작 | 2026-04-19 | `done` | 쿼리 → Qdrant → FlashRank reranking → gpt-4o-mini E2E |
| M3: 품질 개선 | - | `todo` | 청킹 최적화, 임베딩 모델 실험, 평가 지표 도입 |
| M4: API 제공 | 2026-04-19 | `done` | FastAPI REST API 4개 엔드포인트, Streamlit UI |
| M5: 배포 | - | `todo` | 운영 환경 배포, 모니터링 |

---

## 단기 (이번 스프린트)

### TASK-001: BGE-reranker-v2-m3 도입 (재순위 다국어화)
**우선순위**: 최우선
**배경**: 현재 FlashRank `ms-marco-MiniLM-L-12-v2`는 영어 학습 cross-encoder라 한국어 질의 + 영문 문서 크로스에서 오작동. "ROS의 주요 구성요소는?" 질의가 한국어 딥러닝 문서의 "CONTENTS" 섹션을 0.988점, 실제 ROS 청크를 0.059점으로 평가한 사례 확인 (ADR-011)
**목표**: 한↔영 크로스 retrieval 품질을 가시적으로 개선
**범위**: 재순위 단계만. 임베딩(`text-embedding-3-small`)·Qdrant 컬렉션은 유지 → **재인덱싱 불필요**

**서브태스크**:
- [ ] 의존성 추가 — `FlagEmbedding` 또는 `sentence-transformers` 중 채택 결정 (FlagEmbedding이 BGE 공식)
- [ ] `.env`에 `RERANKER_BACKEND=flashrank|bge-m3` 토글 변수 + `RERANKER_MODEL_NAME` 추가
- [ ] `apps/config.py`에 동일 필드 추가
- [ ] `packages/rag/retriever.py` 재작성:
  - 추상화: `class Reranker(Protocol): def rerank(query, candidates, top_n) -> list[ScoredChunk]`
  - 구현 2종: `FlashRankReranker`, `BgeM3Reranker` (`BAAI/bge-reranker-v2-m3`)
  - 모델 로드는 프로세스 전역 싱글톤 + 첫 호출 시 lazy init
- [ ] 첫 로드 시간(~30~60초)을 `apps/main.py` lifespan에서 미리 warm-up할지 결정
- [ ] 동일 질의 5건으로 A/B 비교 표 작성, [features/evaluation.md](wiki/features/evaluation.md)에 기록:
  - "ROS의 주요 구성요소는?" / "Robotics Programming 방법은?" / "자율 주행" 등 한↔영 혼합
  - 측정: top-3 소스의 doc_id, 점수, 관련 여부 (수동 라벨)
- [ ] LangSmith 트레이스에 `reranker.backend` 메타데이터 태그 추가
- [ ] 기본값 결정: A/B 결과에 따라 `RERANKER_BACKEND=bge-m3`을 기본으로 할지, flashrank 유지하고 옵트인할지
- [ ] ADR-011 업데이트 또는 ADR-012 신규 작성 (결과 + 결정)
- [ ] changelog.md `[0.6.0]` 항목 추가

**완료 기준**: 동일 한국어 질의에서 ROS 영문 청크가 top-3에 진입, 무관한 한국어 딥러닝 문서가 1위로 올라가는 사례가 사라짐

**주의사항**:
- `bge-reranker-v2-m3` 모델은 ~570MB 다운로드 (HuggingFace Hub)
- GPU 없으면 청크당 100~300ms 추가 latency — `initial_k=20`이면 +2~6초. `initial_k`를 10으로 낮추는 옵션도 같이 고려
- 메모리 ~2GB 추가 점유

### TASK-002: BGE-M3 임베딩 도입 (선택, TASK-001 결과 보고 결정)
TASK-001로도 부족하면 임베딩 자체를 다국어 BGE-M3(1024-d, 로컬, 비용 0)으로 교체. **Qdrant 컬렉션 재생성 + 전체 재인덱싱 필요**. 별도 ADR로 분리. 우선순위: 보류.

---

## 중기 (1~3개월)

- [ ] 
- [ ] 

---

## 장기 / 검토 중

- [x] Reranking 도입 (FlashRank 로컬, 2026-04-19)
- [x] 멀티모달 (이미지 포함 PDF) — Docling으로 기본 지원
- [x] 대화 히스토리 영속화 + 최근 20턴 컨텍스트 주입 (2026-04-21)
- [x] 중복 업로드 방지 L1 (SHA-256 파일 해시, 2026-04-21)
- [x] LangSmith 관측 통합 (2026-04-21)
- [x] 파싱 후 정규화 (2026-04-21)
- [x] FlashRank 재순위 실제 활성화 (2026-04-21) — 단 한↔영 크로스 모델 평가 필요
- [x] HybridChunker(docling-core) 도입 + 전체 heading 경로 breadcrumb 주입 (2026-04-21)
- [x] 원본 파일 영구 보관 (2026-04-21)
- [ ] **다국어 rerank 모델 평가** (bge-reranker-v2-m3 등) — 최우선
- [ ] HybridChunker 토큰 상한 설정 (512 토큰 초과 청크 방지)
- [ ] 중복 감지 L2 (정규화 텍스트 해시) / L3 (임베딩 유사도 경고)
- [ ] 하이브리드 검색 (키워드 + 벡터) — 형태소 분석(Kiwi) 동반 검토
- [ ] 스트리밍 응답
- [ ] 사용자 피드백 루프
- [ ] 평가 지표 측정 (Precision@K, Recall@K, MRR)
- [ ] 인증 (API Key 또는 OAuth)
- [ ] 대화 요약(summary) 메모리 — 긴 세션 초기 문맥 보존

---

## 완료된 항목

| 항목 | 완료일 |
|------|--------|
| 위키 초기 구조 설정 | 2026-04-17 |
| 전체 RAG 파이프라인 구현 (M1·M2·M4) | 2026-04-19 |
| 대화 히스토리 DB 저장 + 최근 20턴 컨텍스트 주입 | 2026-04-21 |
| 중복 업로드 방지 L1 (SHA-256 파일 해시) | 2026-04-21 |
| LangSmith 관측 통합 (`@traceable` + 세션 태그 + 단계별 타이머) | 2026-04-21 |
| 파싱 후 정규화 (단어 분리 복구·페이지 번호 제거 등) | 2026-04-21 |
| 모바일 업로드 호환 + 상한 200MB + score_threshold 튜닝 | 2026-04-21 |
| HybridChunker + 전체 heading 경로 breadcrumb + 페이지 번호 복구 | 2026-04-21 |
| 원본 파일 영구 보관 (재인덱싱 가능 구조) | 2026-04-21 |
| FlashRank 재순위 실제 활성화 | 2026-04-21 |
| 기존 6개 문서 마크다운 fallback으로 재인덱싱 완료 (ROS PDF 1619→800청크) | 2026-04-21 |
