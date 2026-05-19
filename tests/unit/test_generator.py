import json
from unittest.mock import MagicMock

from packages.code.models import ScoredChunk
from packages.rag.generator import generate, generate_suggestions, _ground_suggestions


def _make_chunk(content: str, content_type: str = "text") -> ScoredChunk:
    return ScoredChunk(
        content=content,
        metadata={"content_type": content_type, "doc_id": "doc-1"},
        score=0.9,
    )


# --- generate(): {"answer", "suggestions"} dict 반환 (TASK-007 이후) ---

def test_generate_returns_answer_dict():
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = MagicMock(content="답변입니다.")

    chunks = [_make_chunk("컨텍스트 내용")]
    result = generate(llm=mock_llm, question="질문은?", chunks=chunks)

    assert result["answer"] == "답변입니다."
    assert result["suggestions"] == []
    mock_llm.invoke.assert_called_once()


def test_generate_includes_table_context():
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = MagicMock(content="테이블 답변")

    chunks = [_make_chunk("| A | B |\n|---|---|\n| 1 | 2 |", "table")]
    result = generate(llm=mock_llm, question="표에서 B의 값은?", chunks=chunks)
    assert result["answer"] == "테이블 답변"


def test_generate_empty_chunks():
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = MagicMock(content="정보 없음")

    result = generate(llm=mock_llm, question="질문", chunks=[])
    assert result["answer"] == "정보 없음"


# --- TASK-026: 후속 질문 grounding (_ground_suggestions) ---

def test_ground_suggestions_keeps_evidence_in_chunk():
    """evidence가 청크 본문에 (공백 무시) 있으면 통과."""
    chunks = [_make_chunk("ROS는 노드와 토픽으로 메시지를 주고받는다.")]
    items = [{"q": "노드란 무엇인가?", "source": "『ROS』 p.1", "evidence": "노드와 토픽으로"}]
    assert _ground_suggestions(items, chunks, 3) == ["노드란 무엇인가?"]


def test_ground_suggestions_drops_unverified_evidence():
    """evidence가 청크에 없으면 폐기 — LLM이 지어낸 질문을 거른다."""
    chunks = [_make_chunk("ROS는 노드와 토픽으로 메시지를 주고받는다.")]
    items = [{"q": "딥러닝 학습률은?", "source": "『ROS』 p.1", "evidence": "경사하강법 적용"}]
    assert _ground_suggestions(items, chunks, 3) == []


def test_ground_suggestions_drops_too_short_evidence():
    """우연 매칭될 만큼 짧은 evidence는 검증 무의미 — 폐기."""
    chunks = [_make_chunk("ROS는 노드와 토픽으로 메시지를 주고받는다.")]
    items = [{"q": "노드?", "source": "『ROS』 p.1", "evidence": "는"}]
    assert _ground_suggestions(items, chunks, 3) == []


def test_ground_suggestions_ignores_non_dict_items():
    """스키마를 벗어난 평문 문자열 항목은 검증 불가 — 폐기."""
    chunks = [_make_chunk("ROS는 노드와 토픽으로 메시지를 주고받는다.")]
    assert _ground_suggestions(["그냥 문자열 질문"], chunks, 3) == []


def test_ground_suggestions_respects_count():
    """검증 통과분이 count를 넘으면 상위 count개만 반환."""
    chunks = [_make_chunk("가나다라마바사 아자차카타파하")]
    items = [{"q": f"q{i}", "source": "s", "evidence": "가나다라마"} for i in range(5)]
    assert len(_ground_suggestions(items, chunks, 3)) == 3


# --- TASK-026: generate_suggestions (스트리밍 경로) ---

def test_generate_suggestions_grounded():
    """JSON 응답을 evidence 검증 후 q 문자열만 반환."""
    chunks = [_make_chunk("ROS는 노드와 토픽으로 메시지를 주고받는다.")]
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = MagicMock(content=json.dumps({
        "suggestions": [
            {"q": "노드 통신 방식은?", "source": "『ROS』 p.1", "evidence": "노드와 토픽으로"},
            {"q": "GPU 메모리 관리는?", "source": "『ROS』 p.1", "evidence": "CUDA 스트림"},
        ]
    }))
    result = generate_suggestions(mock_llm, "ROS 구성요소?", "답변 내용", chunks, 3)
    assert result == ["노드 통신 방식은?"]  # 두 번째는 evidence 미검증으로 폐기


def test_generate_suggestions_empty_on_insufficient_answer():
    """답변이 '정보 없음' 류면 LLM 호출 없이 빈 배열."""
    chunks = [_make_chunk("내용")]
    mock_llm = MagicMock()
    result = generate_suggestions(mock_llm, "질문", "관련 문서를 찾지 못했습니다.", chunks, 3)
    assert result == []
    mock_llm.invoke.assert_not_called()


def test_generate_suggestions_empty_on_no_chunks():
    """청크가 없으면 grounding 불가 — LLM 호출 없이 빈 배열."""
    mock_llm = MagicMock()
    assert generate_suggestions(mock_llm, "질문", "정상 답변", [], 3) == []
    mock_llm.invoke.assert_not_called()


# --- TASK-026: generate(suggestions_enabled=True) (비스트리밍 경로) ---

def test_generate_with_suggestions_enabled():
    """JSON answer+suggestions 파싱 후 suggestions를 evidence 검증."""
    chunks = [_make_chunk("ROS는 노드와 토픽으로 메시지를 주고받는다.")]
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = MagicMock(content=json.dumps({
        "answer": "ROS는 노드 기반입니다.",
        "suggestions": [
            {"q": "토픽이란?", "source": "『ROS』 p.1", "evidence": "노드와 토픽으로"},
        ],
    }))
    result = generate(
        llm=mock_llm, question="ROS?", chunks=chunks,
        suggestions_enabled=True, suggestions_count=3,
    )
    assert result["answer"] == "ROS는 노드 기반입니다."
    assert result["suggestions"] == ["토픽이란?"]
