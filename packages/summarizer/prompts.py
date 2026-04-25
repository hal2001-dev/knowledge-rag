"""TASK-014 (ADR-024) 문서 요약 프롬프트.

목표:
- 환각 차단 — 문서에 명시된 어휘만 사용, 불확실하면 빈 배열 허용
- 한국어 자연스러움 우선 (사용자가 카탈로그·랜딩에서 매일 보는 텍스트)
- JSON 스키마 강제, 후처리 없이 그대로 DB 저장
"""

SUMMARY_SCHEMA_DESCRIPTION = """\
{
  "one_liner":         "문서 한 줄 요약 (한국어, 40자 이내, 마침표 없음)",
  "abstract":          "문서 개요 (한국어, 3~5문장)",
  "topics":            ["핵심 주제 키워드 3~7개 (한국어 또는 원문 용어)"],
  "target_audience":   "예: 'ROS 입문자', '딥러닝 중급자' — 모르면 빈 문자열",
  "sample_questions":  ["이 문서로 답할 수 있는 구체적 질문 정확히 3개"]
}\
"""

SYSTEM_PROMPT = f"""당신은 기술 문서 요약 전문가입니다. 사용자가 RAG 지식 도서관에서 문서를 빠르게 식별할 수 있도록 객관적이고 충실한 요약을 만듭니다.

**반드시 지킬 규칙**
1. 출력은 아래 JSON 스키마와 정확히 동일한 키 구성으로 응답한다.
2. **문서에 명시되지 않은 사실/주장/주제를 절대 만들지 않는다.** 추측·일반론 금지.
3. 확신이 없으면 비운다: `topics`는 빈 배열, `target_audience`는 빈 문자열, `sample_questions`는 빈 배열.
4. `one_liner`는 40자 이내, 마침표 없이. `abstract`는 3~5문장.
5. `sample_questions`는 정확히 3개. 문서로 답할 수 있는 구체적 질문 — "이 문서는 무엇인가요?" 같은 메타 질문 금지.
6. 외국어 도서이거나 한국어 사용자에게 가치 있는 한국어 표현이 명백한 경우 한국어로 요약하되, 고유명사·기술 용어는 원문 표기를 유지한다.

**JSON 스키마**
{SUMMARY_SCHEMA_DESCRIPTION}
"""


FEW_SHOT_EXAMPLES = [
    {
        "title": "Programming Robots with ROS",
        "head": (
            "Chapter 1. Introduction\n"
            "ROS (Robot Operating System) is a flexible framework for writing robot software. "
            "It is a collection of tools, libraries, and conventions that aim to simplify the "
            "task of creating complex and robust robot behavior across a wide variety of robotic "
            "platforms.\n\n"
            "Chapter 2. Preliminaries\n"
            "Before writing your first program, you'll set up an Ubuntu environment, install ROS "
            "Kinetic, and configure your workspace using catkin..."
        ),
        "expected": {
            "one_liner": "ROS 기반 로봇 프로그래밍 입문 실습서",
            "abstract": (
                "ROS(Robot Operating System)의 핵심 개념과 도구를 실습 예제로 소개하는 입문서이다. "
                "Ubuntu 환경 셋업과 catkin 워크스페이스 구성부터 시작해 노드·토픽·메시지 기반 "
                "통신 모델을 단계별로 다룬다. 실제 로봇 플랫폼에서 동작하는 행동 코드를 작성하는 "
                "흐름을 따라간다."
            ),
            "topics": ["ROS", "Robot Operating System", "catkin", "노드/토픽 통신", "로봇 프로그래밍"],
            "target_audience": "ROS 입문자",
            "sample_questions": [
                "ROS 워크스페이스를 catkin으로 설정하는 방법은?",
                "ROS의 노드와 토픽은 어떻게 통신하는가?",
                "Ubuntu에서 ROS Kinetic을 설치하려면 어떤 절차가 필요한가?",
            ],
        },
    },
    {
        "title": "회사 분기 보고서",
        "head": (
            "표지 — 2024년 4분기 실적 발표 자료. 매출, 영업이익, 사업부별 KPI 정리. "
            "내부 임직원 회람용."
        ),
        "expected": {
            "one_liner": "2024년 4분기 실적 발표 내부 자료",
            "abstract": (
                "2024년 4분기 매출과 영업이익을 사업부별로 정리한 내부 회람 자료이다. "
                "공개된 본문 분량이 짧아 세부 KPI 수치는 확인되지 않는다."
            ),
            "topics": ["분기 실적", "사업부 KPI", "내부 보고"],
            "target_audience": "",
            "sample_questions": [],
        },
    },
]


def build_user_prompt(title: str, head_text: str) -> str:
    """문서 제목과 첫 5~10청크의 본문(약 2~4K 토큰)을 입력으로 묶는다."""
    return (
        f"문서 제목: {title}\n\n"
        f"문서 앞부분 본문:\n```\n{head_text.strip()}\n```\n\n"
        f"이 문서를 위 규칙에 따라 JSON으로 요약하세요."
    )


def build_few_shot_messages() -> list[dict]:
    """OpenAI chat messages 형식의 few-shot 예시. system 다음, 실제 user 직전에 삽입."""
    msgs: list[dict] = []
    import json as _json
    for ex in FEW_SHOT_EXAMPLES:
        msgs.append({"role": "user", "content": build_user_prompt(ex["title"], ex["head"])})
        msgs.append({"role": "assistant", "content": _json.dumps(ex["expected"], ensure_ascii=False)})
    return msgs
