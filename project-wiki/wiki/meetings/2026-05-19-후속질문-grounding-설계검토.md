# 2026-05-19: 후속 질문 grounding 설계 검토

**참석자**: 사용자(1인 운영자), Claude
**관련 페이지**: [roadmap.md](../../roadmap.md) (TASK-026), [ISSUE-007](../issues/open/ISSUE-007-overview-suggested-questions-mismatch.md)
**원본**: raw/meetings/2026-05-19-후속질문-grounding-설계검토.md

## 요약
답변 아래 후속 질문(suggestions)이 문서 내용에 입각하지 않고 "LLM이 만들어낸" 느낌이라는 사용자 관찰에서 출발. 원인을 진단하고 청크 근거 기반 grounding 보완안을 확정, TASK-026으로 등록.

## 논의 내용
- **현황**: 후속 질문은 검색이 아니라 LLM 생성. 스트리밍 경로 `generate_suggestions()`는 청크 없이 `question + answer`만 입력받고, 프롬프트가 "자연스럽게 물어볼 질문"이라는 통념적 상상을 요구. 비스트리밍 경로는 청크가 context에 있어도 활용 지시 없음.
- **문제**: 답변은 본문의 추상화 결과 → 거기서 질문을 파생하면 2차 추상화로 책 고유 디테일 소실. ISSUE-007(예시 질문 ↔ retrieval 불일치)과 동일 근본 문제.
- **선택지**: 답변 기반(현행)·청크만·하이브리드. grounding 강제 레버 A(프롬프트 교체)·B(source/evidence 검증·폐기)·C(retrieval 재검증) 비교.
- **청크 확보**: 스트리밍 경로에서 청크는 `pipeline.py:290`의 로컬 변수를 재사용 — 재검색 불필요, 인자 1개 추가만으로 가능.
- **비용·성능**: 실측(`answers_2026-05-14`) 기반 — 스트리밍 호출당 +$0.0006(~3.7배, 월 +$2~18), 후속 질문 칩 지연 +2초 이내 목표. 비스트리밍 경로는 추가 비용 ≈ 0.

## 결정 사항
- 보완 범위 = **레버 A + B** (청크 투입 + grounding 프롬프트 + `{q,source,evidence}` 검증·폐기). 레버 C는 효과 대비 비용이 커서 제외 → [roadmap.md](../../roadmap.md) TASK-026 설계 결정 반영
- 두 경로(비스트리밍/스트리밍) 프롬프트·스키마 통일, INSUFFICIENT 가드 유지
- TASK-026으로 등록, 신규 ADR-037은 착수 시 확정 (decisions.md 반영 예정)

## 액션 아이템
- [x] TASK-026 roadmap 등록 + 위키 동기화 (2026-05-19)
- [ ] TASK-025 done 마감 후 TASK-026 착수
- [ ] 착수 시 ADR-037 작성, `bench_answers.py` grounding 비교 지표 확장

## 다음 회의
TASK-026 착수 시점 (TASK-025 완료 후)
