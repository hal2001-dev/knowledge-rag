---
name: ISSUE-003 인덱싱 중 메모리 폭발로 시스템 멈춤
description: QdrantDocumentStore.add_documents가 모든 청크를 한 번에 임베딩·PointStruct로 보유해 큰 문서에서 RAM이 GB 단위로 폭증, 시스템이 응답 불가 상태가 됨
type: issue
---

# ISSUE-003: 인덱싱 중 메모리 폭발로 시스템 멈춤

**상태**: resolved
**발생일**: 2026-04-26
**해결일**: 2026-04-26
**관련 기능**: [ingestion.md](../../features/ingestion.md), [embedding.md](../../features/embedding.md) _(미작성)_

---

## 증상

- `bulk_ingest --via-queue` 또는 HTTP 인제스트 도중 워커 프로세스의 RSS가 GB 단위로 급증
- 큰 문서(수천 청크 PDF)에서 OS swap 폭주 → 시스템 전반이 응답 불가, 강제 종료 외 회복 불가
- OOM 즉시 종료가 아닌 점진적 freeze 양상 (스왑 의존)

## 원인 분석

[packages/vectorstore/qdrant_store.py](../../../../packages/vectorstore/qdrant_store.py) `QdrantDocumentStore.add_documents`(hybrid 분기)가 **단일 호출에서**
다음을 모두 메모리에 동시 보유했습니다.

1. `texts = [d.content for d in documents]` — 전체 청크 텍스트 리스트
2. `dense_vecs = self._embeddings.embed_documents(texts)` — 전체 청크 dense 벡터 (1536d × N)
3. `sparse_vecs = self._sparse.embed_documents(texts)` — 전체 청크 sparse 벡터
4. `points: list[PointStruct] = [...]` — 모든 청크의 벡터+payload(원문 텍스트 포함)

배치 분할은 **upsert 단계(UPSERT_BATCH_SIZE=256)에서만** 적용되고, 임베딩·PointStruct 구성은 전부 펼친 상태로 진행되었습니다. 따라서 한 시점 메모리 점유는 대략

```
peak ≈ N_chunks × (dense_dim × 4B + sparse_payload + 텍스트 원문)
```

수천 청크 문서에서는 수백 MB ~ 수 GB. 로컬 임베딩 모델(bge-m3 등) 사용 시 모델 메모리와 합쳐져 더 가파르게 증가.

근본 원인 두 가지:
- **임베딩 단계 배치화 누락** — upsert만 배치, embed는 일괄
- **PointStruct를 폐기 없이 누적** — 전체 청크 분량 객체가 GC 대상이 안 됨

## 해결 방법

[packages/vectorstore/qdrant_store.py](../../../../packages/vectorstore/qdrant_store.py)에 `EMBED_BATCH_SIZE = 64` 상수를 도입하고, `add_documents`의 hybrid 분기를 다음 루프로 재구성했습니다.

```
for start in range(0, total, EMBED_BATCH_SIZE):
    chunk_docs = documents[start:start + EMBED_BATCH_SIZE]
    texts      = [d.content for d in chunk_docs]
    dense_vecs = self._embeddings.embed_documents(texts)
    sparse_vecs = self._sparse.embed_documents(texts)
    points = [PointStruct(...) for ...]
    for u_start in range(0, len(points), UPSERT_BATCH_SIZE):
        self._client.upsert(... points[u_start:u_start+UPSERT_BATCH_SIZE])
    # 루프 종료 시 chunk_docs/texts/dense_vecs/sparse_vecs/points GC
```

효과:
- 한 시점 메모리 점유가 **64청크 ×(벡터+텍스트)** 로 캡 — 수 MB 수준
- `UPSERT_BATCH_SIZE=256`(Qdrant payload 한도 회피)는 그대로 유지되며, embed_batch < upsert_batch 관계라 추가 분할은 1배치로 끝남
- vector(`search_mode == "vector"`) 분기는 langchain QdrantVectorStore에 위임되므로 손대지 않음 (해당 라이브러리 내부 배치 동작)

로그에 `embed_batch`/`upsert_batch` 둘 다 출력되도록 메시지 갱신.

## 재발 방지

- **배치 캡은 임베딩·PointStruct 구성 단계에서 걸어야 한다** — upsert만 배치하는 것은 메모리 보호가 아니라 네트워크 보호일 뿐
- 신규 인제스트 경로 추가 시(예: 다른 벡터 스토어, 다른 임베딩 모델) 같은 패턴이 재현될 수 있음. 대량 리스트 전체에 한 번에 함수 적용하지 말고 **배치 루프**로 감쌀 것
- 추가로 점검할 메모리 핫스팟(현재는 손대지 않음, 후속 과제):
  - [scripts/bulk_ingest.py](../../../../scripts/bulk_ingest.py) `read_bytes()` — 큰 파일 통째 메모리 로드 (SHA-256 계산용). 8MB 청크 streaming hash로 변경 가능
  - [apps/routers/ingest.py](../../../../apps/routers/ingest.py) `await file.read()` — 업로드 본문 통째 메모리 수신
  - [packages/loaders/docling_loader.py](../../../../packages/loaders/docling_loader.py) — Docling 자체가 문서 통째 파싱 (라이브러리 한계, 우회 어려움)
- 동시 워커가 여러 개일 때는 위 점유가 워커 수만큼 곱해지므로, 워커 수와 `EMBED_BATCH_SIZE`는 RAM 예산에 맞춰 같이 보고 조정

## 출처

- 코드: `packages/vectorstore/qdrant_store.py` `add_documents`
- 트리거: 사용자 보고 — bulk 인덱싱 중 시스템 freeze (2026-04-26 세션)

---

## 후속 발견 (2026-04-26 추가 진단)

0.23.3 fix 이후에도 동일 증상(시스템 freeze) 재발 보고를 받고 진단한 결과, **본 fix는 임베딩 단계만 캡**하고 다음은 미해결로 남아 있음을 확인했습니다.

### 1. 실제 freeze 트리거 — 워커 동시 기동
- 사용자가 `apps.indexer_worker`를 실수로 2개 띄운 상태에서 큰 PDF 처리 시 합산 RSS 14~16GB → swap 폭주 → freeze
- 단일 워커는 같은 PDF에서 RSS 5~12GB 사용해도 sys_free 90~97%로 안정 운행 (175잡 100% 처리 검증)
- `apps.indexer_worker`에 동시 기동 가드(pidfile 또는 Postgres advisory lock) 부재가 운영 함정

### 2. Docling 파싱 단계 무캡 — [ISSUE-004](../open/ISSUE-004-docling-parse-longtail.md)로 분리
- 파싱 단계가 단일 잡 처리 시간의 90~96%, RSS의 거의 전체를 차지
- 청크 수와 RSS 무관 — PDF 페이지·테이블 그래프 자체 비용
- 라이브러리 외부 의존이라 우회 비용 큼, 후순위 별도 이슈로 트래킹

### 3. `_save_markdown` 이중 파싱 (코드 결함)
- [packages/loaders/docling_loader.py:54-55, 146-149](../../../../packages/loaders/docling_loader.py#L146-L149)에서 `markdown_save_dir` 켜져 있으면 같은 PDF를 `_DoclingLoader.load()`로 두 번 호출
- [apps/config.py:36](../../../../apps/config.py#L36)의 `markdown_dir` 기본값이 `./data/markdown`이라 `.env` 미설정 시 자동 활성 — 단일 잡당 메모리·시간 사실상 2배
- 본 fix는 이 결함과 별개 — 후속 P1 작업으로 정리 필요

### 4. stale `in_progress` 잡 누수
- 워커 SIGKILL로 끊긴 잡(이번엔 #39, #40)이 `status='in_progress'`로 영원히 잠김 — 다른 워커도 `FOR UPDATE SKIP LOCKED`로 안 잡음
- 워커 시작 시 N분 이상 in_progress 잡을 자동 reset하는 housekeeping 부재

### 결론

본 ISSUE-003 자체(임베딩 미배치)는 해결 상태 그대로 유지(resolved). 단 freeze 종합 대응은 미완:
- **P0**: 워커 동시 기동 가드 + stale in_progress 자동 reset
- **P1**: `_save_markdown` 이중 파싱 제거
- **P2**: `INDEXER_MAX_JOBS` 도입 (누적형 안전망)
- **P3**: [ISSUE-004](../open/ISSUE-004-docling-parse-longtail.md) — Docling 파싱 단계 메모리·시간 long-tail
