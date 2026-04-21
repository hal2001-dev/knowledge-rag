from pathlib import Path

import streamlit as st
import requests

API_BASE = "http://localhost:8000"

st.set_page_config(
    page_title="Knowledge RAG",
    page_icon="📚",
    layout="wide",
)

st.title("📚 Knowledge RAG")

# ─── 사이드바: 문서 업로드 ───────────────────────────────────────────────────
with st.sidebar:
    st.header("문서 업로드")
    # 모바일 호환: type 화이트리스트는 MIME 미지정 파일(.md 등)을 회색 처리하므로 제거.
    # 서버(apps/routers/ingest.py)에서 확장자 검증한다.
    uploaded_file = st.file_uploader(
        "파일 선택",
        help="PDF, TXT, Markdown, DOCX 지원",
        key="uploader",
    )
    if uploaded_file is not None:
        ext = Path(uploaded_file.name).suffix.lower()
        allowed = {".pdf", ".txt", ".md", ".docx"}
        size_kb = len(uploaded_file.getvalue()) / 1024
        if ext not in allowed:
            st.warning(f"지원하지 않는 형식: {ext} (PDF/TXT/MD/DOCX만 허용)")
        else:
            st.caption(f"선택됨: **{uploaded_file.name}** ({size_kb:,.1f} KB)")

    title_input = st.text_input("문서 제목", placeholder="제목을 입력하세요")
    source_input = st.text_input("출처 (선택)", placeholder="URL 또는 설명")

    if st.button("업로드 & 인덱싱", type="primary", use_container_width=True):
        if not uploaded_file:
            st.error("파일을 선택하세요.")
        elif not title_input:
            st.error("제목을 입력하세요.")
        else:
            with st.spinner("문서 처리 중... (첫 실행 시 Docling 모델 다운로드로 수 분 걸릴 수 있습니다)"):
                try:
                    resp = requests.post(
                        f"{API_BASE}/ingest",
                        files={"file": (uploaded_file.name, uploaded_file.getvalue())},
                        data={"title": title_input, "source": source_input},
                        timeout=1800,
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        st.success(f"완료! {data['chunk_count']}개 청크 인덱싱됨")
                        if data["has_tables"]:
                            st.info("테이블 감지됨")
                        if data["has_images"]:
                            st.info("이미지 감지됨")
                        st.session_state.pop("documents_cache", None)
                    elif resp.status_code == 409:
                        detail = resp.json().get("detail", {})
                        if isinstance(detail, dict):
                            st.warning(
                                f"이미 등록된 문서입니다: **{detail.get('title', '?')}** "
                                f"(doc_id: `{detail.get('doc_id', '?')}`)"
                            )
                        else:
                            st.warning(str(detail))
                    else:
                        st.error(f"오류: {resp.json().get('detail', resp.text)}")
                except requests.exceptions.ConnectionError:
                    st.error("API 서버에 연결할 수 없습니다. 서버가 실행 중인지 확인하세요.")

    st.divider()

    # 문서 목록
    st.header("인덱싱된 문서")
    if st.button("목록 새로고침", use_container_width=True):
        st.session_state.pop("documents_cache", None)

    if "documents_cache" not in st.session_state:
        try:
            resp = requests.get(f"{API_BASE}/documents", timeout=10)
            st.session_state["documents_cache"] = resp.json() if resp.status_code == 200 else {"documents": [], "total": 0}
        except requests.exceptions.ConnectionError:
            st.session_state["documents_cache"] = {"documents": [], "total": 0}

    docs_data = st.session_state["documents_cache"]
    docs = docs_data.get("documents", [])

    if not docs:
        st.caption("아직 인덱싱된 문서가 없습니다.")
    else:
        st.caption(f"총 {docs_data['total']}개 문서")
        for doc in docs:
            with st.expander(f"📄 {doc['title']}", expanded=False):
                st.caption(f"타입: {doc['file_type'].upper()}  |  청크: {doc['chunk_count']}개")
                badges = []
                if doc["has_tables"]:
                    badges.append("테이블")
                if doc["has_images"]:
                    badges.append("이미지")
                if badges:
                    st.caption("포함: " + ", ".join(badges))
                st.caption(f"인덱싱: {doc['indexed_at'][:10]}")
                if st.button("삭제", key=f"del_{doc['doc_id']}", type="secondary"):
                    with st.spinner("삭제 중..."):
                        resp = requests.delete(f"{API_BASE}/documents/{doc['doc_id']}", timeout=10)
                        if resp.status_code == 200:
                            st.success("삭제 완료")
                            st.session_state.pop("documents_cache", None)
                            st.rerun()
                        else:
                            st.error("삭제 실패")


# ─── 메인: 채팅 인터페이스 ──────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state["messages"] = []
if "session_id" not in st.session_state:
    st.session_state["session_id"] = None

# 대화 기록 출력
for msg in st.session_state["messages"]:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg["role"] == "assistant" and msg.get("sources"):
            with st.expander(f"📎 소스 {len(msg['sources'])}개 ({msg.get('latency_ms', 0)}ms)"):
                for src in msg["sources"]:
                    badge = {"table": "🗂️", "image": "🖼️", "text": "📝"}.get(src["content_type"], "📝")
                    st.markdown(
                        f"{badge} **{src['title']}** — p.{src.get('page', '?')}  "
                        f"`score: {src['score']:.3f}`"
                    )
                    st.caption(src["excerpt"])
                    st.divider()

# 입력창
if question := st.chat_input("문서에 대해 질문하세요..."):
    st.session_state["messages"].append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("검색 및 답변 생성 중..."):
            try:
                resp = requests.post(
                    f"{API_BASE}/query",
                    json={
                        "question": question,
                        "session_id": st.session_state["session_id"],
                    },
                    timeout=60,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    answer = data["answer"]
                    sources = data["sources"]
                    latency_ms = data["latency_ms"]
                    st.session_state["session_id"] = data.get("session_id")

                    st.markdown(answer)
                    if sources:
                        with st.expander(f"📎 소스 {len(sources)}개 ({latency_ms}ms)"):
                            for src in sources:
                                badge = {"table": "🗂️", "image": "🖼️", "text": "📝"}.get(src["content_type"], "📝")
                                st.markdown(
                                    f"{badge} **{src['title']}** — p.{src.get('page', '?')}  "
                                    f"`score: {src['score']:.3f}`"
                                )
                                st.caption(src["excerpt"])
                                st.divider()

                    st.session_state["messages"].append({
                        "role": "assistant",
                        "content": answer,
                        "sources": sources,
                        "latency_ms": latency_ms,
                    })
                else:
                    err = resp.json().get("detail", resp.text)
                    st.error(f"오류: {err}")
                    st.session_state["messages"].append({"role": "assistant", "content": f"오류: {err}"})

            except requests.exceptions.ConnectionError:
                msg = "API 서버에 연결할 수 없습니다."
                st.error(msg)
                st.session_state["messages"].append({"role": "assistant", "content": msg})

# 대화 초기화 버튼
if st.session_state["messages"]:
    if st.button("대화 초기화", type="secondary"):
        st.session_state["messages"] = []
        st.session_state["session_id"] = None
        st.rerun()
