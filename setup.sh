#!/bin/bash
set -e

echo "=== RAG 프로젝트 환경 설정 ==="

# Python 버전 확인 (3.10 이상)
PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null)
PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)

if [ "$PYTHON_MAJOR" -lt 3 ] || { [ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 10 ]; }; then
    echo "❌ Python 3.10+ 필요 (현재: $PYTHON_VERSION)"
    exit 1
fi
echo "→ Python $PYTHON_VERSION 감지"

# 가상환경 생성
if [ ! -d ".venv" ]; then
    echo "→ 가상환경 생성 중..."
    python3 -m venv .venv
fi

# 가상환경 활성화
source .venv/bin/activate

# pip 업그레이드 및 의존성 설치
echo "→ 의존성 설치 중..."
pip install --upgrade pip -q
pip install -r requirements.txt -q

# .env 파일 생성
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "→ .env 파일 생성됨. OPENAI_API_KEY를 입력하세요."
fi

# data 디렉터리 생성
mkdir -p data/uploads data/qdrant_storage data/pg_data

echo ""
echo "✅ 환경 설정 완료!"
echo ""
echo "다음 단계:"
echo "  1. source .venv/bin/activate   # 가상환경 활성화"
echo "  2. .env 파일에 OPENAI_API_KEY 입력"
echo "  3. docker compose up -d        # Qdrant + PostgreSQL 기동"
echo "  4. uvicorn apps.main:app --reload  # API 서버 기동"
