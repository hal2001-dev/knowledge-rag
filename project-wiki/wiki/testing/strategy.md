# 테스트 전략 (Testing Strategy)

**상태**: draft
**마지막 업데이트**: 2026-04-17
**관련 페이지**: [evaluation.md](../features/evaluation.md), `cases.md` _(미작성)_

---

## 테스트 레벨

| 레벨 | 범위 | 도구 | 상태 |
|------|------|------|------|
| Unit | 개별 함수 (파서, 청커, 임베딩 호출) | pytest | `todo` |
| Integration | 파이프라인 E2E (ingest → query) | pytest | `todo` |
| Evaluation | 검색/답변 품질 | 직접 구현 or RAGAS | `todo` |
| Load | 동시 요청 성능 | locust | `todo` |

---

## 단위 테스트 범위

| 모듈 | 테스트 항목 |
|------|------------|
| `parser.py` | PDF 파싱, 빈 파일 처리, 인코딩 |
| `chunker.py` | chunk_size 준수, overlap 적용, 빈 chunk 필터링 |
| `embedder.py` | 벡터 차원 확인, batch 처리, API 오류 처리 |
| `retriever.py` | Top-K 반환, score threshold 필터링 |
| `generator.py` | 프롬프트 포맷, 응답 파싱 |

---

## 통합 테스트 시나리오

1. 샘플 PDF 업로드 → 인덱싱 → 질문 → 답변 포함 출처 확인
2. 관련 없는 질문 → "찾을 수 없음" 응답 확인
3. 한국어 문서에 한국어 질문
4. 대용량 파일 (50MB) 처리

---

## 평가 (RAG 품질)

RAGAS 또는 자체 평가 세트 사용:
- Ground truth Q&A 셋 필요 → [evaluation.md](../features/evaluation.md)
- 지표: Precision@3, Recall@3, Faithfulness, Answer Relevance

---

## 실행 방법

```bash
# 전체 테스트
pytest tests/

# 특정 모듈
pytest tests/test_chunker.py -v

# 커버리지
pytest --cov=src tests/
```

---

## 테스트 데이터

| 파일 | 용도 |
|------|------|
| `tests/fixtures/sample.pdf` | 기본 파싱 테스트용 |
| `tests/fixtures/qa_set.json` | 평가용 Q&A 셋 |
