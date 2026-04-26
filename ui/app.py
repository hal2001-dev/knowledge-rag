"""Knowledge RAG — 통합 UI (TASK-005 1단계, wiki/features/admin_ui.md 참고)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Streamlit이 ui/app.py 단독 실행 시 프로젝트 루트가 sys.path에 없어
# `from apps.config import ...` 가 실패. 여기서 명시적으로 주입.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import requests
import streamlit as st

API_BASE = "http://localhost:8000"
EVAL_DIR = Path(__file__).parent.parent / "data" / "eval_runs"

st.set_page_config(page_title="Knowledge RAG", page_icon="📚", layout="wide")

# ─── 세션 상태 초기값 ─────────────────────────────────────────
st.session_state.setdefault("messages", [])                  # 채팅 로그
st.session_state.setdefault("session_id", None)              # 현재 RAG 세션
st.session_state.setdefault("documents_cache", None)
st.session_state.setdefault("conversations_cache", None)
st.session_state.setdefault("selected_doc_id", None)
st.session_state.setdefault("selected_session_id", None)
# TASK-016: 도서관 탭 → 채팅 탭 doc_filter 라우팅
st.session_state.setdefault("active_doc_filter", None)       # {"doc_id", "title"} 또는 None
st.session_state.setdefault("library_expanded_doc", None)    # 카드 상세 토글

st.title("📚 Knowledge RAG")

TAB_CHAT, TAB_LIBRARY, TAB_DOCS, TAB_JOBS, TAB_CONVOS, TAB_SYSTEM, TAB_EVAL = st.tabs(
    ["💬 채팅", "📚 도서관", "📄 문서", "🛠️ 잡", "💭 대화", "⚙️ 시스템", "📊 평가"]
)


# ─── 공통 헬퍼 ───────────────────────────────────────────────
def _api_get(path: str, params: dict | None = None, timeout: int = 10):
    try:
        r = requests.get(f"{API_BASE}{path}", params=params, timeout=timeout)
        return r.status_code, (r.json() if r.status_code < 500 else r.text)
    except requests.exceptions.ConnectionError:
        return None, None


def _api_delete(path: str, timeout: int = 10):
    try:
        r = requests.delete(f"{API_BASE}{path}", timeout=timeout)
        return r.status_code, (r.json() if r.status_code < 500 else r.text)
    except requests.exceptions.ConnectionError:
        return None, None


# ═════════════════════════════════════════════════════════════
# 탭 1: 채팅
# ═════════════════════════════════════════════════════════════
with TAB_CHAT:
    col_main, col_sid = st.columns([4, 1])
    with col_sid:
        sid = st.session_state["session_id"]
        st.caption(f"세션: `{sid[:8]}...`" if sid else "세션: (미생성)")
        if st.session_state["messages"] and st.button("대화 초기화", type="secondary"):
            st.session_state["messages"] = []
            st.session_state["session_id"] = None
            st.rerun()

    # TASK-016: 도서관 탭에서 라우팅된 doc_filter 활성 표시 + 해제
    active_filter = st.session_state.get("active_doc_filter")
    if active_filter:
        bf_col_msg, bf_col_clear = st.columns([5, 1])
        with bf_col_msg:
            st.info(
                f"📖 **{active_filter['title'][:60]}** 에 한정해 답변합니다.",
                icon="📚",
            )
        with bf_col_clear:
            if st.button("전체 검색", help="문서 한정 해제", key="clear_doc_filter"):
                st.session_state["active_doc_filter"] = None
                st.rerun()

    def _render_suggestions(suggestions: list[str], key_prefix: str):
        """답변 아래에 후속 질문 배지 렌더.

        st.button 클릭은 자체로 rerun을 유발하므로 명시적 st.rerun() 호출 안 함.
        수동 호출 시 두 번째 이후 클릭에서 state가 꼬이는 케이스가 관찰됨.
        """
        if not suggestions:
            return
        st.caption("💡 이어서 물을 질문")
        cols = st.columns(max(len(suggestions), 1))
        for i, sug in enumerate(suggestions):
            if cols[i].button(sug, key=f"{key_prefix}_sug_{i}", use_container_width=True):
                st.session_state["_pending_question"] = sug

    # 빈 채팅 empty state — 인덱스 요약 + 예시 질문 + 주제 칩 + 최근 문서 (TASK-008/017)
    if not st.session_state["messages"]:
        if st.session_state.get("_index_overview") is None:
            code, data = _api_get("/index/overview", timeout=30)
            st.session_state["_index_overview"] = data if code == 200 else {}
        ov = st.session_state["_index_overview"] or {}
        if ov.get("doc_count", 0) > 0:
            with st.container(border=True):
                st.markdown("#### 👋 이 시스템이 아는 내용")
                if ov.get("summary"):
                    st.markdown(ov["summary"])

                # TASK-017: 카테고리 분포 — 도서관 탭 진입 안내
                cats_dist = ov.get("categories") or []
                if cats_dist:
                    parts = [f"**{c['label']}** {c['count']}" for c in cats_dist[:6]]
                    st.caption("📂 카테고리: " + " · ".join(parts) + "  (도서관 탭에서 탐색)")

                # TASK-017: 주제 칩 — 클릭 시 도서관 탭의 검색 박스 사전 채우기 후 이동
                top_tags = ov.get("top_tags") or []
                if top_tags:
                    st.caption("🏷️ 자주 등장하는 주제 (클릭하면 도서관에서 검색)")
                    chip_cols = st.columns(min(len(top_tags), 6) or 1)
                    for i, tag in enumerate(top_tags[:6]):
                        col = chip_cols[i % len(chip_cols)]
                        if col.button(tag, key=f"land_tag_{i}", use_container_width=True):
                            st.session_state["library_search"] = tag
                            st.toast(f"🔍 '{tag}' 검색어를 도서관 탭에 채웠습니다", icon="📚")

                if ov.get("suggested_questions"):
                    st.caption("🎯 예시 질문 (클릭하면 바로 질의됩니다)")
                    cols = st.columns(min(len(ov["suggested_questions"]), 3) or 1)
                    for i, q in enumerate(ov["suggested_questions"]):
                        col = cols[i % len(cols)]
                        if col.button(q, key=f"example_q_{i}", use_container_width=True):
                            st.session_state["_pending_question"] = q

                # TASK-017: 최근 문서 카드 — 클릭 시 doc_filter 활성 + 사용자가 다음 질문 입력
                recent = ov.get("recent_docs") or []
                if recent:
                    st.caption("📖 최근 추가된 문서 (클릭하면 해당 책에 한정해 질의)")
                    rc_cols = st.columns(min(len(recent), 3) or 1)
                    for i, d in enumerate(recent[:6]):
                        col = rc_cols[i % len(rc_cols)]
                        with col, st.container(border=True):
                            st.markdown(f"**{d['title'][:48]}**")
                            if d.get("one_liner"):
                                st.caption(d["one_liner"])
                            elif d.get("category"):
                                st.caption(f"_{d['category']}_")
                            if st.button(
                                "이 책에 대해 묻기", key=f"land_recent_{d['doc_id']}",
                                use_container_width=True,
                            ):
                                st.session_state["active_doc_filter"] = {
                                    "doc_id": d["doc_id"], "title": d["title"]
                                }
                                st.toast(f"📖 '{d['title'][:40]}' 한정 모드 활성화", icon="📚")

                if ov.get("titles"):
                    with st.expander(f"전체 문서 {ov.get('doc_count', 0)}개 (도서관 탭으로)"):
                        for t in ov["titles"]:
                            st.caption(f"• {t}")
        elif ov.get("summary"):
            st.info(ov["summary"])

    for msg_idx, msg in enumerate(st.session_state["messages"]):
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg["role"] == "assistant" and msg.get("sources"):
                with st.expander(f"📎 소스 {len(msg['sources'])}개 ({msg.get('latency_ms', 0)}ms)"):
                    for src in msg["sources"]:
                        badge = {"table": "🗂️", "image": "🖼️", "text": "📝"}.get(src["content_type"], "📝")
                        st.markdown(f"{badge} **{src['title']}** — p.{src.get('page', '?')}  `score: {src['score']:.3f}`")
                        st.caption(src["excerpt"])
                        st.divider()
        # 버튼은 `st.chat_message` 컨테이너 바깥에 렌더.
        # key는 반드시 msg_idx 기반으로 통일 — 라이브 렌더와 다음 rerun의 히스토리 렌더가
        # 같은 key를 써야 Streamlit이 클릭 이벤트를 매칭할 수 있음.
        if msg["role"] == "assistant" and msg.get("suggestions"):
            _render_suggestions(msg["suggestions"], key_prefix=f"msg_{msg_idx}")

    # 배지 클릭으로 자동 질의 대기 상태인 경우 질문으로 사용
    pending = st.session_state.pop("_pending_question", None)
    question = pending or st.chat_input("문서에 대해 질문하세요...")
    if question:
        st.session_state["messages"].append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)
        new_suggestions: list[str] = []
        with st.chat_message("assistant"):
            with st.spinner("검색 및 답변 생성 중..."):
                try:
                    payload = {
                        "question": question,
                        "session_id": st.session_state["session_id"],
                    }
                    if st.session_state.get("active_doc_filter"):
                        payload["doc_filter"] = st.session_state["active_doc_filter"]["doc_id"]
                    resp = requests.post(
                        f"{API_BASE}/query",
                        json=payload,
                        timeout=60,
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        st.session_state["session_id"] = data.get("session_id")
                        st.markdown(data["answer"])
                        if data["sources"]:
                            with st.expander(f"📎 소스 {len(data['sources'])}개 ({data['latency_ms']}ms)"):
                                for src in data["sources"]:
                                    badge = {"table": "🗂️", "image": "🖼️", "text": "📝"}.get(src["content_type"], "📝")
                                    st.markdown(f"{badge} **{src['title']}** — p.{src.get('page', '?')}  `score: {src['score']:.3f}`")
                                    st.caption(src["excerpt"])
                                    st.divider()
                        new_suggestions = data.get("suggestions", [])
                        st.session_state["messages"].append({
                            "role": "assistant", "content": data["answer"],
                            "sources": data["sources"], "latency_ms": data["latency_ms"],
                            "suggestions": new_suggestions,
                        })
                    else:
                        err = resp.json().get("detail", resp.text)
                        st.error(f"오류: {err}")
                        st.session_state["messages"].append({"role": "assistant", "content": f"오류: {err}"})
                except requests.exceptions.ConnectionError:
                    msg = "API 서버에 연결할 수 없습니다."
                    st.error(msg)
                    st.session_state["messages"].append({"role": "assistant", "content": msg})
        # suggestions 배지는 `st.chat_message` 컨테이너 바깥에 렌더.
        # key는 방금 append된 assistant 메시지의 인덱스 — 다음 rerun의 히스토리 루프에서
        # 동일 msg_idx로 재렌더되므로 Streamlit widget state가 일관되게 매칭됨.
        if new_suggestions:
            assistant_idx = len(st.session_state["messages"]) - 1
            _render_suggestions(new_suggestions, key_prefix=f"msg_{assistant_idx}")


# ═════════════════════════════════════════════════════════════
# 탭 2: 도서관 (TASK-016)
# ═════════════════════════════════════════════════════════════
with TAB_LIBRARY:
    st.caption("인덱싱된 문서를 카테고리·요약으로 탐색하고, 특정 문서에 대해 바로 질문할 수 있습니다.")

    # 데이터 로드 — 채팅 탭과 동일 캐시 재사용
    if st.session_state["documents_cache"] is None:
        code, data = _api_get("/documents", timeout=10)
        st.session_state["documents_cache"] = data if code == 200 else {"documents": [], "total": 0}

    lib_docs_data = st.session_state["documents_cache"] or {"documents": [], "total": 0}
    lib_docs = lib_docs_data.get("documents", [])

    if not lib_docs:
        st.info("아직 인덱싱된 문서가 없습니다. **문서** 탭에서 업로드해 보세요.")
    else:
        # 필터 바 ─────────────────────────────────────────────
        f_col_q, f_col_type, f_col_cat = st.columns([3, 1, 2])
        with f_col_q:
            search_q = st.text_input(
                "검색", placeholder="제목·요약·태그…", key="library_search",
                label_visibility="collapsed",
            )
        with f_col_type:
            doc_type_options = sorted({d.get("doc_type") or "book" for d in lib_docs})
            doc_type_filter = st.selectbox(
                "형식", options=["(전체)"] + doc_type_options,
                key="library_doc_type", label_visibility="collapsed",
            )
        with f_col_cat:
            cat_options = sorted({d.get("category") for d in lib_docs if d.get("category")})
            category_filter = st.selectbox(
                "카테고리",
                options=["(전체)"] + cat_options + ["(미분류)"],
                key="library_category", label_visibility="collapsed",
            )

        # 필터 적용
        def _matches(d: dict) -> bool:
            if doc_type_filter != "(전체)" and (d.get("doc_type") or "book") != doc_type_filter:
                return False
            cat = d.get("category")
            if category_filter == "(미분류)":
                if cat:
                    return False
            elif category_filter != "(전체)":
                if cat != category_filter:
                    return False
            if search_q:
                q = search_q.lower().strip()
                hay_parts = [
                    d.get("title", ""),
                    (d.get("summary") or {}).get("one_liner", "") or "",
                    (d.get("summary") or {}).get("abstract", "") or "",
                    " ".join((d.get("summary") or {}).get("topics") or []),
                    " ".join(d.get("tags") or []),
                ]
                hay = " ".join(p.lower() for p in hay_parts if p)
                if q not in hay:
                    return False
            return True

        filtered = [d for d in lib_docs if _matches(d)]

        # 카테고리 그룹핑 — 동일 카테고리는 한 섹션, "(미분류)"는 마지막
        from collections import defaultdict as _dd
        groups: dict[str, list[dict]] = _dd(list)
        for d in filtered:
            groups[d.get("category") or "(미분류)"].append(d)

        st.caption(f"총 {len(filtered)}/{len(lib_docs)}개 문서")

        ordered_keys = sorted([k for k in groups if k != "(미분류)"]) + (
            ["(미분류)"] if "(미분류)" in groups else []
        )

        for cat_key in ordered_keys:
            docs_in_cat = groups[cat_key]
            with st.container():
                st.markdown(f"#### {cat_key}  ·  {len(docs_in_cat)}")
                # 3-column 카드 그리드
                cols = st.columns(3)
                for i, d in enumerate(docs_in_cat):
                    col = cols[i % 3]
                    with col, st.container(border=True):
                        doc_id = d["doc_id"]
                        title = d["title"][:60]
                        sm = d.get("summary") or {}
                        one_liner = sm.get("one_liner") or ""
                        topics = (sm.get("topics") or [])[:5]
                        conf = d.get("category_confidence")
                        review_badge = ""
                        if conf is not None and conf < 0.4:
                            review_badge = " ⚠️"

                        st.markdown(f"**{title}**{review_badge}")
                        if one_liner:
                            st.caption(one_liner)
                        else:
                            st.caption("_요약 생성 중…_")
                        if topics:
                            st.caption("· " + " · ".join(topics))

                        b_detail, b_ask = st.columns(2)
                        if b_detail.button("상세", key=f"lib_detail_{doc_id}", use_container_width=True):
                            st.session_state["library_expanded_doc"] = (
                                None if st.session_state["library_expanded_doc"] == doc_id else doc_id
                            )
                        if b_ask.button(
                            "이 책에 대해 묻기", key=f"lib_ask_{doc_id}",
                            use_container_width=True, type="primary",
                        ):
                            st.session_state["active_doc_filter"] = {
                                "doc_id": doc_id, "title": d["title"]
                            }
                            # 사용자가 첫 질문을 정해 입력하도록 채팅 탭으로 이동만 유도
                            st.toast(f"📖 '{d['title'][:40]}' 한정 모드 활성화 — 채팅 탭으로 이동", icon="📚")

                        # 카드 상세 expander — library_expanded_doc 토글로 표시
                        if st.session_state["library_expanded_doc"] == doc_id:
                            st.divider()
                            if sm.get("abstract"):
                                st.markdown(sm["abstract"])
                            sample_qs = sm.get("sample_questions") or []
                            if sample_qs:
                                st.caption("💡 이 책에서 나올 수 있는 질문")
                                for j, q in enumerate(sample_qs):
                                    if st.button(
                                        q, key=f"lib_sq_{doc_id}_{j}",
                                        use_container_width=True,
                                    ):
                                        st.session_state["active_doc_filter"] = {
                                            "doc_id": doc_id, "title": d["title"]
                                        }
                                        st.session_state["_pending_question"] = q
                                        st.toast("📖 질문 전달 — 채팅 탭에서 응답을 확인하세요", icon="💬")
                            meta_lines = []
                            if d.get("source"):
                                meta_lines.append(f"source: `{d['source'][:60]}`")
                            if d.get("file_type"):
                                meta_lines.append(f"형식: `{d['file_type']}`")
                            if d.get("indexed_at"):
                                meta_lines.append(f"인덱싱: `{d['indexed_at'][:10]}`")
                            if conf is not None:
                                meta_lines.append(f"신뢰도: `{conf}`")
                            if meta_lines:
                                st.caption(" · ".join(meta_lines))


# ═════════════════════════════════════════════════════════════
# 탭 3: 문서
# ═════════════════════════════════════════════════════════════
with TAB_DOCS:
    st.subheader("업로드")
    up_col1, up_col2 = st.columns([2, 3])
    with up_col1:
        uploaded_file = st.file_uploader("파일 선택", help="PDF/TXT/MD/DOCX", key="uploader")
        if uploaded_file is not None:
            ext = Path(uploaded_file.name).suffix.lower()
            allowed = {".pdf", ".txt", ".md", ".docx"}
            size_kb = len(uploaded_file.getvalue()) / 1024
            if ext not in allowed:
                st.warning(f"지원하지 않는 형식: {ext}")
            else:
                st.caption(f"선택됨: **{uploaded_file.name}** ({size_kb:,.1f} KB)")
    with up_col2:
        title_input = st.text_input("문서 제목", placeholder="제목")
        source_input = st.text_input("출처 (선택)", placeholder="URL 또는 설명")
        if st.button("업로드 & 인덱싱", type="primary"):
            if not uploaded_file:
                st.error("파일을 선택하세요.")
            elif not title_input:
                st.error("제목을 입력하세요.")
            else:
                with st.spinner("문서 처리 중... (최대 수 분)"):
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
                            st.session_state["documents_cache"] = None
                            st.session_state["_index_overview"] = None
                        elif resp.status_code == 409:
                            detail = resp.json().get("detail", {})
                            if isinstance(detail, dict):
                                st.warning(f"이미 등록된 문서: **{detail.get('title')}** (doc_id `{detail.get('doc_id')}`)")
                            else:
                                st.warning(str(detail))
                        else:
                            st.error(f"오류: {resp.json().get('detail', resp.text)}")
                    except requests.exceptions.ConnectionError:
                        st.error("API 서버 연결 실패")

    st.divider()

    list_col, refresh_col = st.columns([5, 1])
    with list_col:
        st.subheader("인덱싱된 문서")
    with refresh_col:
        if st.button("새로고침", key="docs_refresh"):
            st.session_state["documents_cache"] = None

    if st.session_state["documents_cache"] is None:
        code, data = _api_get("/documents")
        st.session_state["documents_cache"] = data if code == 200 else {"documents": [], "total": 0}

    docs_data = st.session_state["documents_cache"] or {"documents": [], "total": 0}
    docs = docs_data.get("documents", [])
    if not docs:
        st.caption("아직 인덱싱된 문서가 없습니다.")
    else:
        st.caption(f"총 {docs_data.get('total', len(docs))}개 문서")

        # 헤더 행
        h_title, h_type, h_chunks, h_flags, h_date, h_preview, h_delete = st.columns(
            [4, 1, 1, 1, 2, 1, 1]
        )
        h_title.markdown("**문서**")
        h_type.markdown("**형식**")
        h_chunks.markdown("**청크**")
        h_flags.markdown("**포함**")
        h_date.markdown("**인덱싱**")
        h_preview.markdown("**미리보기**")
        h_delete.markdown("**삭제**")
        st.divider()

        # 각 문서 행: 직접 미리보기/삭제 버튼
        for d in docs:
            doc_id = d["doc_id"]
            short_id = doc_id[:8]
            c_title, c_type, c_chunks, c_flags, c_date, c_preview, c_delete = st.columns(
                [4, 1, 1, 1, 2, 1, 1]
            )
            with c_title:
                st.markdown(f"**{d['title'][:70]}**")
                st.caption(f"`{short_id}`  ·  source: {d.get('source', '')[:50] or '-'}")
            c_type.caption(d["file_type"].upper())
            c_chunks.caption(str(d["chunk_count"]))
            flags = []
            if d["has_tables"]:
                flags.append("🗂️")
            if d["has_images"]:
                flags.append("🖼️")
            c_flags.caption(" ".join(flags) or "-")
            c_date.caption(d["indexed_at"][:10])

            if c_preview.button("🔍", key=f"preview_{doc_id}", help="청크 미리보기 (상위 10개)"):
                st.session_state["selected_doc_id"] = doc_id

            if c_delete.button("🗑️", key=f"del_{doc_id}", help="이 문서 삭제"):
                st.session_state[f"_confirm_del_{doc_id}"] = True

            # 삭제 확인
            if st.session_state.get(f"_confirm_del_{doc_id}"):
                with st.container():
                    st.warning(f"정말 **{d['title']}** 문서를 삭제합니까? (벡터 + DB 레코드)")
                    ok_col, cancel_col = st.columns([1, 1])
                    if ok_col.button("확정 삭제", key=f"confirm_del_{doc_id}", type="primary"):
                        with st.spinner("삭제 중..."):
                            code, _ = _api_delete(f"/documents/{doc_id}")
                            if code == 200:
                                st.success(f"삭제 완료: {d['title']}")
                                st.session_state["documents_cache"] = None
                                st.session_state["_index_overview"] = None
                                st.session_state.pop(f"_confirm_del_{doc_id}", None)
                                if st.session_state.get("selected_doc_id") == doc_id:
                                    st.session_state["selected_doc_id"] = None
                                st.rerun()
                            else:
                                st.error("삭제 실패")
                    if cancel_col.button("취소", key=f"cancel_del_{doc_id}"):
                        st.session_state.pop(f"_confirm_del_{doc_id}", None)
                        st.rerun()

            st.divider()

        # 선택된 문서의 청크 미리보기 (🔍 버튼으로 활성화)
        sel = st.session_state.get("selected_doc_id")
        if sel:
            sel_doc = next((d for d in docs if d["doc_id"] == sel), None)
            if sel_doc:
                st.markdown(f"### 🔍 청크 미리보기 — {sel_doc['title']}")
                if st.button("닫기", key="close_preview"):
                    st.session_state["selected_doc_id"] = None
                    st.rerun()
                code, data = _api_get(f"/documents/{sel}/chunks", params={"limit": 10}, timeout=15)
                if code == 200 and data:
                    for i, ch in enumerate(data["chunks"], 1):
                        hp = " > ".join(ch["heading_path"]) if ch["heading_path"] else "(no heading)"
                        with st.expander(
                            f"[{i}] {hp}  ·  p.{ch.get('page', '?')}  ·  {ch['content_type']}",
                            expanded=(i == 1),
                        ):
                            st.caption(f"chunk_index: {ch.get('chunk_index')}")
                            st.code(ch["content"], language=None)
                else:
                    st.error("미리보기 실패")


# ═════════════════════════════════════════════════════════════
# 탭 4: 잡 (TASK-018)
# ═════════════════════════════════════════════════════════════
with TAB_JOBS:
    st.caption("색인 워커가 처리 중인 작업 큐. 큐 모드(`INGEST_MODE=queue`)에서만 의미가 있습니다.")

    head_col, autoref_col, refresh_col = st.columns([4, 1, 1])
    with head_col:
        st.subheader("색인 작업")
    with autoref_col:
        autorefresh = st.toggle("자동 새로고침", value=False, key="jobs_autorefresh")
    with refresh_col:
        if st.button("새로고침", key="jobs_refresh"):
            pass  # rerun trigger

    # 1) 상태별 카운터
    counters: dict[str, int] = {}
    failed_jobs: list[dict] = []
    code, lc = _api_get("/jobs", params={"limit": 200}, timeout=10)
    if code != 200 or not isinstance(lc, dict):
        st.error("API 응답 실패 — uvicorn이 떠 있는지 확인하세요.")
    else:
        all_jobs = lc.get("jobs", [])
        for j in all_jobs:
            counters[j["status"]] = counters.get(j["status"], 0) + 1

        m_col1, m_col2, m_col3, m_col4 = st.columns(4)
        m_col1.metric("pending", counters.get("pending", 0))
        m_col2.metric("in_progress", counters.get("in_progress", 0))
        m_col3.metric("done", counters.get("done", 0))
        m_col4.metric("failed", counters.get("failed", 0))

        st.divider()

        STATUS_BADGE = {
            "pending":     "⏳ pending",
            "in_progress": "⚙️ 진행중",
            "done":        "✅ 완료",
            "failed":      "❌ 실패",
            "cancelled":   "⏹ 취소",
        }

        # 2) 상태별 필터
        STATUS_OPTIONS = ["pending", "in_progress", "done", "failed", "cancelled"]
        present_statuses = [s for s in STATUS_OPTIONS if counters.get(s, 0) > 0]
        selected_statuses = st.multiselect(
            "상태 필터",
            options=STATUS_OPTIONS,
            default=present_statuses or STATUS_OPTIONS,
            format_func=lambda s: f"{STATUS_BADGE.get(s, s)} ({counters.get(s, 0)})",
            key="jobs_status_filter",
            help="비우면 전체. 기본은 큐에 존재하는 상태만 선택.",
        )

        # 3) 최근 잡 표 (필터 적용 후 enqueued_at DESC 30개)
        filtered = [j for j in all_jobs if j["status"] in selected_statuses] if selected_statuses else all_jobs
        recent = sorted(filtered, key=lambda j: j.get("enqueued_at", ""), reverse=True)[:30]
        if not recent:
            st.caption("필터 조건에 해당하는 잡이 없습니다.")
        else:
            st.caption(f"최근 {len(recent)}개 (필터 매칭 {len(filtered)} / 전체 {len(all_jobs)})")
            # 컬럼: ID·상태·제목·retry·enqueued·started·finished·duration·doc_id (TASK-019 한정 동결 해제)
            COL_WIDTHS = [0.5, 0.9, 3.0, 0.6, 1.4, 1.2, 1.2, 0.9, 0.9]
            h = st.columns(COL_WIDTHS)
            for col, label in zip(h, ["**ID**", "**상태**", "**제목**", "**retry**", "**enqueued**", "**started**", "**finished**", "**duration**", "**doc_id**"]):
                col.markdown(label)

            from datetime import datetime, timezone

            def _parse_iso(ts: str | None):
                if not ts:
                    return None
                try:
                    # API는 isoformat, Z 또는 +00:00 형식. fromisoformat이 둘 다 처리(3.11+)
                    return datetime.fromisoformat(ts.replace("Z", "+00:00"))
                except Exception:
                    return None

            def _fmt_duration(secs: float) -> str:
                if secs < 60:
                    return f"{secs:.0f}s"
                m, s = divmod(int(secs), 60)
                if m < 60:
                    return f"{m}m{s:02d}s"
                h, m = divmod(m, 60)
                return f"{h}h{m:02d}m"

            now = datetime.now(timezone.utc)
            for j in recent:
                cells = st.columns(COL_WIDTHS)
                cells[0].caption(f"#{j['id']}")
                cells[1].caption(STATUS_BADGE.get(j["status"], j["status"]))
                cells[2].caption(j["title"][:60])
                cells[3].caption(str(j["retry_count"]))
                cells[4].caption((j.get("enqueued_at", "") or "")[:19].replace("T", " "))
                cells[5].caption((j.get("started_at", "") or "")[:19].replace("T", " ") if j.get("started_at") else "—")
                cells[6].caption((j.get("finished_at", "") or "")[:19].replace("T", " ") if j.get("finished_at") else "—")
                # duration: done/failed → finished-started, in_progress → now-started, 그외 → —
                started_dt = _parse_iso(j.get("started_at"))
                finished_dt = _parse_iso(j.get("finished_at"))
                if j["status"] == "in_progress" and started_dt:
                    cells[7].caption(_fmt_duration((now - started_dt).total_seconds()))
                elif finished_dt and started_dt:
                    cells[7].caption(_fmt_duration((finished_dt - started_dt).total_seconds()))
                else:
                    cells[7].caption("—")
                cells[8].caption((j.get("doc_id") or "")[:8])
                if j["status"] == "failed" and j.get("error"):
                    with st.expander(f"job #{j['id']} 실패 사유"):
                        st.code(j["error"][:1500], language=None)

    # 자동 새로고침 — Streamlit 내장. 5초마다 rerun
    if autorefresh:
        try:
            from streamlit_autorefresh import st_autorefresh  # 선택적 의존성
            st_autorefresh(interval=5_000, key="jobs_autorefresh_tick")
        except ImportError:
            # 폴백: HTML meta refresh (탭 전환 시에도 도는 단점 있음)
            st.caption("ℹ 자동 새로고침은 `streamlit-autorefresh` 패키지가 설치되어야 합니다 (`pip install streamlit-autorefresh`). 현재는 [새로고침] 버튼을 눌러주세요.")


# ═════════════════════════════════════════════════════════════
# 탭 5: 대화
# ═════════════════════════════════════════════════════════════
with TAB_CONVOS:
    head_col, refresh_col = st.columns([5, 1])
    with head_col:
        st.subheader("대화 세션")
    with refresh_col:
        if st.button("새로고침", key="convos_refresh"):
            st.session_state["conversations_cache"] = None

    if st.session_state["conversations_cache"] is None:
        code, data = _api_get("/conversations")
        st.session_state["conversations_cache"] = data if code == 200 else {"conversations": [], "total": 0}

    cdata = st.session_state["conversations_cache"] or {"conversations": [], "total": 0}
    convos = cdata.get("conversations", [])

    if not convos:
        st.caption("아직 생성된 세션이 없습니다.")
    else:
        st.caption(f"총 {cdata.get('total', len(convos))}개 세션 (최근 업데이트 순)")

        table_rows = []
        options = {}
        for c in convos:
            sid = c["session_id"]
            label = f"{c.get('title') or '(제목없음)'}  ·  {sid[:8]}"
            options[label] = sid
            table_rows.append({
                "session_id": sid[:8],
                "title": c.get("title") or "",
                "created_at": str(c.get("created_at", ""))[:19],
                "updated_at": str(c.get("updated_at", ""))[:19],
            })
        st.dataframe(table_rows, use_container_width=True, hide_index=True)

        picked = st.selectbox("세션 선택", ["(선택)"] + list(options), key="convo_picker")
        if picked != "(선택)":
            sid = options[picked]
            st.session_state["selected_session_id"] = sid
            code, detail = _api_get(f"/conversations/{sid}", timeout=10)
            c1, c2 = st.columns([4, 1])
            with c1:
                st.markdown(f"**세션 `{sid}`**")
            with c2:
                if st.button("🗑️ 세션 삭제", key="convo_del_btn", type="secondary"):
                    code, _ = _api_delete(f"/conversations/{sid}")
                    if code == 200:
                        st.success("삭제 완료")
                        st.session_state["conversations_cache"] = None
                        st.session_state["selected_session_id"] = None
                        st.rerun()
                    else:
                        st.error("삭제 실패")

            if code == 200 and detail:
                messages = detail.get("messages", [])
                if not messages:
                    st.caption("메시지가 없습니다 (빈 세션).")
                else:
                    for m in messages:
                        with st.chat_message(m["role"]):
                            st.markdown(m["content"])
                            st.caption(str(m["created_at"])[:19])


# ═════════════════════════════════════════════════════════════
# 탭 4: 시스템 (읽기 전용)
# ═════════════════════════════════════════════════════════════
with TAB_SYSTEM:
    st.subheader("시스템 상태 (읽기 전용)")
    st.caption("설정 변경은 `.env` 편집 후 `uvicorn` 재시작으로만 반영됩니다.")

    # API 측으로 config·상태 한 번에 가져오는 엔드포인트가 없으므로 여기서 직접 settings/qdrant 조회
    try:
        from apps.config import get_settings
        from qdrant_client import QdrantClient
        settings = get_settings()

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("### 🔄 Reranker")
            st.metric("Backend", settings.reranker_backend)
            st.caption(f"모델: `{settings.reranker_model_name or '(기본)'}`")

            st.markdown("### 🤖 LLM")
            st.metric("Backend", settings.llm_backend)
            st.caption(f"모델: `{settings.llm_model or settings.openai_chat_model}`")
            st.caption(f"base_url: `{settings.llm_base_url or '(기본)'}`")
            temp = (settings.llm_temperature or "").strip()
            st.caption(f"temperature: {temp or settings.openai_chat_temperature}")

        with c2:
            st.markdown("### 🧩 Embedding")
            st.metric("Backend", settings.embedding_backend)
            st.caption(f"모델: `{settings.embedding_model_name or ('text-embedding-3-small' if settings.embedding_backend == 'openai' else 'BAAI/bge-m3')}`")

            st.markdown("### 🗃 Qdrant")
            try:
                from packages.vectorstore.qdrant_store import DENSE_NAME
                qc = QdrantClient(url=settings.qdrant_url)
                info = qc.get_collection(settings.qdrant_collection)
                st.metric("Points", info.points_count)
                st.caption(f"컬렉션: `{settings.qdrant_collection}`")
                vecs = info.config.params.vectors
                if isinstance(vecs, dict):
                    dense = vecs.get(DENSE_NAME)
                    sparse_cfg = getattr(info.config.params, "sparse_vectors", None) or {}
                    sparse_keys = ", ".join(sparse_cfg.keys()) if sparse_cfg else "(없음)"
                    st.caption(
                        f"mode: hybrid · dense({DENSE_NAME}) dim={dense.size} "
                        f"distance={dense.distance} · sparse=[{sparse_keys}]"
                    )
                else:
                    st.caption(f"mode: vector · dim={vecs.size} distance={vecs.distance}")
                st.caption(f"status: `{info.status}`")
            except Exception as e:
                st.error(f"Qdrant 연결 실패: {e}")

        st.divider()
        c3, c4 = st.columns(2)
        with c3:
            st.markdown("### 🟢 API Health")
            code, data = _api_get("/health", timeout=3)
            if code == 200:
                st.success(f"{API_BASE} OK")
            else:
                st.error(f"{API_BASE} 응답 없음")
        with c4:
            st.markdown("### 📡 LangSmith")
            if settings.langchain_tracing_v2 and settings.langchain_api_key:
                st.success(f"활성 · 프로젝트: `{settings.langchain_project}`")
                st.markdown(f"[대시보드 열기 →](https://smith.langchain.com)")
            else:
                st.caption("비활성")
    except Exception as e:
        st.error(f"설정 로드 실패: {e}")


# ═════════════════════════════════════════════════════════════
# 탭 5: 평가
# ═════════════════════════════════════════════════════════════
with TAB_EVAL:
    st.subheader("평가 지표 (data/eval_runs/*.json)")
    st.caption("실행: `python scripts/bench_retrieval.py` / `python scripts/bench_answers.py`")

    if not EVAL_DIR.exists():
        st.info("아직 실행 이력이 없습니다.")
    else:
        retrieval_files = sorted(EVAL_DIR.glob("retrieval_*.json"), reverse=True)
        answers_files = sorted(EVAL_DIR.glob("answers_*.json"), reverse=True)

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("### 🎯 Retrieval (최신)")
            if retrieval_files:
                latest = json.loads(retrieval_files[0].read_text())
                for run in latest.get("runs", []):
                    agg = run.get("aggregate", {})
                    st.caption(f"backend: **{run['backend']}**  ·  {retrieval_files[0].name}")
                    sc1, sc2, sc3, sc4 = st.columns(4)
                    sc1.metric("Hit@K", agg.get("hit@k"))
                    sc2.metric("Precision@K", agg.get("precision"))
                    sc3.metric("Recall@K", agg.get("recall"))
                    sc4.metric("MRR", agg.get("mrr"))
            else:
                st.caption("retrieval 결과 없음")

        with c2:
            st.markdown("### 📝 Answer (Ragas, 최신)")
            if answers_files:
                latest = json.loads(answers_files[0].read_text())
                agg = latest.get("aggregate", {})
                cfg = latest.get("settings", {})
                st.caption(f"LLM: **{cfg.get('llm_backend')}:{cfg.get('llm_model')}**  ·  rerank: **{cfg.get('reranker_backend')}**")
                st.caption(f"{answers_files[0].name}")
                sa1, sa2 = st.columns(2)
                sa1.metric("Faithfulness", agg.get("faithfulness"))
                sa2.metric("Answer relevancy", agg.get("answer_relevancy"))
                sa3, sa4 = st.columns(2)
                sa3.metric("Context precision", agg.get("llm_context_precision_without_reference"))
                sa4.metric("Context recall", agg.get("context_recall"))
            else:
                st.caption("answer 결과 없음")

        st.divider()
        st.markdown("### 🕑 히스토리 (최근 10개)")

        from datetime import datetime, timezone

        def _fmt_ts(raw: str) -> str:
            """파일명 타임스탬프(예: 2026-04-22T001606Z)를 `2026-04-22 09:16:06 KST`로."""
            try:
                dt = datetime.strptime(raw, "%Y-%m-%dT%H%M%SZ").replace(tzinfo=timezone.utc)
                kst = dt.astimezone()  # 로컬타임존
                return kst.strftime("%Y-%m-%d %H:%M:%S %Z") or kst.strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                return raw

        def _hist(files, kind):
            rows = []
            for f in files[:10]:
                try:
                    d = json.loads(f.read_text())
                    raw_ts = f.stem.split("_", 1)[1] if "_" in f.stem else f.stem
                    ts = _fmt_ts(raw_ts)
                    if kind == "retrieval":
                        for run in d.get("runs", []):
                            agg = run.get("aggregate", {})
                            rows.append({
                                "time": ts, "kind": "retrieval",
                                "backend": run.get("backend", ""),
                                "Hit@K": agg.get("hit@k"), "P@K": agg.get("precision"),
                                "R@K": agg.get("recall"), "MRR": agg.get("mrr"),
                            })
                    else:
                        agg = d.get("aggregate", {})
                        cfg = d.get("settings", {})
                        rows.append({
                            "time": ts, "kind": "answer",
                            "backend": f"{cfg.get('llm_backend','')}:{cfg.get('llm_model','')}",
                            "faith": agg.get("faithfulness"),
                            "answer_rel": agg.get("answer_relevancy"),
                            "ctx_prec": agg.get("llm_context_precision_without_reference"),
                            "ctx_rec": agg.get("context_recall"),
                        })
                except Exception:
                    continue
            return rows

        hist = _hist(retrieval_files, "retrieval") + _hist(answers_files, "answer")
        if hist:
            st.dataframe(hist, use_container_width=True, hide_index=True)
        else:
            st.caption("히스토리 없음")
