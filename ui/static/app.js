/* Knowledge RAG — vanilla chat UI
 * ────────────────────────────────────────────────────────────────
 * 구조 개요
 *  - 빌드 도구 없이 브라우저에서 바로 동작하는 단일 파일 (FastAPI `/ui/` 정적 마운트).
 *  - 상태(state) → render() 한 번에 DOM 전체 재구성. 가상 DOM은 없고
 *    메시지 수가 적은 채팅 UX 특성상 innerHTML 초기화 후 다시 그리는 방식이 충분.
 *  - 백엔드 통신:
 *      · GET  /conversations/{id}  : 영속화된 메시지 동기화
 *      · POST /query/stream        : SSE 스트림 (meta/sources/token/suggestions/done/error)
 *  - 인증: localhost origin 은 FastAPI 측에서 admin 으로 자동 매핑 (헤더 미사용).
 *  - 외부 의존성(CDN): marked, DOMPurify, highlight.js, Tailwind.
 *
 * SSE 이벤트 의미
 *   meta        : 신규 세션 id 통보 (첫 응답 시)
 *   sources     : 검색 컨텍스트 카드 목록 (token 보다 먼저 도착)
 *   token       : LLM 토큰 (문자열 누적)
 *   suggestions : 후속 질문 칩 배열
 *   done        : latency_ms 등 마무리 메타
 *   error       : 사람이 읽을 수 있는 오류 메시지
 */
(() => {
  "use strict";

  // 같은 origin(`/ui/`) 으로 서빙되면 빈 문자열로 두고 상대 경로 fetch.
  // 다른 호스트에서 열 때는 index.html 에서 `window.__API_BASE__` 를 주입.
  const API_BASE = window.__API_BASE__ ?? "";

  // ───────────────── 마크다운 파이프라인 ─────────────────
  // 렌더 흐름: LLM 텍스트 → marked(파싱) → DOMPurify(살균) → innerHTML → hljs(하이라이트).
  // DOMPurify 를 거치지 않으면 응답에 섞인 `<script>` / `onclick=` 등이 그대로 실행될 수 있음.
  marked.setOptions({
    gfm: true,     // 표·체크박스 등 GitHub Flavored Markdown
    breaks: true,  // 줄바꿈을 <br> 로 — 채팅은 문단이 짧고 줄바꿈이 자주 의미를 가짐
  });

  function renderMarkdown(text) {
    const raw = marked.parse(text || "");
    // ADD_ATTR: ["target"] — 링크의 `target="_blank"` 를 살균 단계에서 보존.
    return DOMPurify.sanitize(raw, { ADD_ATTR: ["target"] });
  }

  function highlightWithin(root) {
    // marked 가 만든 <pre><code class="language-…"> 블록에만 하이라이트 적용.
    // hljs 가 가끔 클래스 미감지 시 throw — 다른 코드 블록까지 깨지 않도록 swallow.
    root.querySelectorAll("pre code").forEach((el) => {
      try {
        hljs.highlightElement(el);
      } catch (_) {}
    });
  }

  // ───────────────── DOM 참조 ─────────────────
  // index.html 의 정적 노드를 한 번만 캐싱. 동적 노드(메시지/소스/칩)는 render() 가 매번 새로 만든다.
  const $scroll = document.getElementById("scroll");
  const $messages = document.getElementById("messages");
  const $empty = document.getElementById("empty");
  const $status = document.getElementById("status");
  const $error = document.getElementById("error");
  const $input = document.getElementById("input");
  const $form = document.getElementById("form");
  const $send = document.getElementById("send");
  const $cancel = document.getElementById("cancel");
  const $newChat = document.getElementById("new-chat");
  const $sessionPill = document.getElementById("session-pill");
  // 사이드바 / 리사이저 관련 노드.
  const $app = document.getElementById("app");
  const $sidebar = document.getElementById("sidebar");
  const $convoList = document.getElementById("convo-list");
  const $convoCount = document.getElementById("convo-count");
  const $resizer = document.getElementById("resizer");
  const $sidebarToggle = document.getElementById("sidebar-toggle");
  const $backdrop = document.getElementById("backdrop");

  // ───────────────── 상태 ─────────────────
  // sessionId 우선순위: URL 쿼리 > localStorage > 새 세션(null).
  // URL 우선이라서 링크 공유 시 같은 세션을 그대로 이어볼 수 있다.
  const url = new URL(location.href);
  const state = {
    sessionId:
      url.searchParams.get("session_id") ||
      localStorage.getItem("session_id") ||
      null,
    // 서버에서 확정된(영속화된) 메시지 목록. {role, content, sources?, latency_ms?, suggestions?}
    messages: [],
    // 사이드바에 표시할 대화 목록. {session_id, title, updated_at} — GET /conversations 결과.
    conversations: [],
    // 옵티미스틱 user 메시지 — 서버 응답을 기다리지 않고 즉시 버블로 표시.
    // 스트림이 끝나면 loadSession() 으로 messages 와 합쳐지면서 null 로 비워진다.
    pendingUser: null,
    // 토큰 이벤트로 누적되는 어시스턴트 본문 (스트리밍 중에만 사용).
    streamingAnswer: "",
    // sources / suggestions / latency 는 token 보다 먼저 또는 따로 도착하므로 별도 보관.
    // render() 단계에서 마지막 assistant 버블에 머지된다.
    liveSources: null,
    liveLatency: undefined,
    liveSuggestions: [],
    // 스트림 진행 중 플래그 — 전송 버튼/중지 버튼 토글과 중복 전송 방지에 사용.
    isPending: false,
    // 진행 중 fetch 의 AbortController. 사용자가 중지/새 채팅을 누르면 abort().
    abort: null,
    // 사용자가 거의 바닥에 머물러 있으면 새 토큰 도착마다 자동 스크롤(sticky).
    // 위로 스크롤해 과거를 보고 있을 때는 끌어내리지 않는다.
    sticky: true,
  };

  // ───────────────── 세션 ─────────────────
  // URL / localStorage / 헤더 pill — 세션 식별자를 세 위치에 동시 반영해서
  // 새로고침·링크 공유·탭 재방문 어느 경로로 들어와도 같은 대화가 복원되게 한다.
  function syncSessionUrl() {
    const u = new URL(location.href);
    if (state.sessionId) u.searchParams.set("session_id", state.sessionId);
    else u.searchParams.delete("session_id");
    // pushState 가 아니라 replaceState — 히스토리 스택을 더럽히지 않기 위함.
    history.replaceState({}, "", u);
    $sessionPill.textContent = state.sessionId
      ? `session: ${state.sessionId.slice(0, 8)}`
      : "";
  }

  function setSession(id) {
    state.sessionId = id || null;
    if (id) localStorage.setItem("session_id", id);
    else localStorage.removeItem("session_id");
    syncSessionUrl();
  }

  async function loadSession() {
    if (!state.sessionId) {
      render();
      return;
    }
    try {
      const res = await fetch(
        `${API_BASE}/conversations/${state.sessionId}`,
      );
      if (!res.ok) {
        // 서버가 잊은 세션(예: 만료/삭제)이면 클라이언트 상태도 비워서 새 채팅처럼 시작.
        if (res.status === 404) setSession(null);
        render();
        return;
      }
      const data = await res.json();
      // 본문만 채우고 sources/suggestions 등 메타는 stream 이벤트에서 다시 채워진다
      // — 영속화된 첨부 메타를 굳이 동기화하지 않는 이유는, 현재 백엔드가
      //   `/conversations/{id}` 응답에 role/content 만 보장하기 때문.
      state.messages = (data.messages || []).map((m) => ({
        role: m.role,
        content: m.content,
      }));
      syncSessionUrl();
      render();
      scrollToBottom(true);
    } catch (e) {
      console.error(e);
      render();
    }
  }

  // ───────────────── 사이드바 (대화 목록) ─────────────────
  // GET /conversations 로 목록을 받아 사이드바에 그린다. 항목 클릭 → 세션 전환.
  // 목록은 updated_at desc 정렬 상태로 도착하므로 그대로 사용한다.
  async function loadConversations() {
    try {
      const res = await fetch(`${API_BASE}/conversations`);
      if (!res.ok) return;
      const data = await res.json();
      state.conversations = data.conversations || [];
      renderSidebar();
    } catch (e) {
      // 목록 로드 실패는 채팅 기능을 막지 않는다 — 조용히 무시하고 빈 목록 유지.
      console.error(e);
    }
  }

  // 상대 시간 표기 ("방금", "5분 전", "3일 전", 그 이상은 날짜).
  function relativeTime(iso) {
    if (!iso) return "";
    const then = new Date(iso).getTime();
    if (Number.isNaN(then)) return "";
    const diff = Date.now() - then;
    const min = Math.floor(diff / 60000);
    if (min < 1) return "방금";
    if (min < 60) return `${min}분 전`;
    const hr = Math.floor(min / 60);
    if (hr < 24) return `${hr}시간 전`;
    const day = Math.floor(hr / 24);
    if (day < 7) return `${day}일 전`;
    const d = new Date(then);
    return `${d.getMonth() + 1}/${d.getDate()}`;
  }

  function renderSidebar() {
    $convoList.innerHTML = "";

    if (!state.conversations.length) {
      const empty = document.createElement("div");
      empty.className = "convo-empty";
      empty.textContent = "아직 대화가 없습니다.";
      $convoList.appendChild(empty);
      $convoCount.textContent = "";
      return;
    }

    state.conversations.forEach((c) => {
      const item = document.createElement("div");
      item.className =
        "convo-item" + (c.session_id === state.sessionId ? " active" : "");
      item.tabIndex = 0;
      item.setAttribute("role", "button");

      const title = document.createElement("span");
      title.className = "convo-title";
      title.textContent = c.title?.trim() || "제목 없는 대화";
      title.title = title.textContent;

      const time = document.createElement("span");
      time.className = "convo-time";
      time.textContent = relativeTime(c.updated_at);

      const del = document.createElement("button");
      del.type = "button";
      del.className = "convo-del";
      del.setAttribute("aria-label", "대화 삭제");
      del.innerHTML = `<svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6 6 18M6 6l12 12"/></svg>`;
      del.addEventListener("click", (e) => {
        // 항목 클릭(세션 전환)과 분리.
        e.stopPropagation();
        deleteConversation(c.session_id, c.title);
      });

      const activate = () => switchSession(c.session_id);
      item.addEventListener("click", activate);
      item.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          activate();
        }
      });

      item.appendChild(title);
      item.appendChild(time);
      item.appendChild(del);
      $convoList.appendChild(item);
    });

    $convoCount.textContent = `대화 ${state.conversations.length}개`;
  }

  // 사이드바 항목 클릭 → 해당 세션 로드. 진행 중 스트림은 끊고 라이브 상태 초기화.
  function switchSession(id) {
    if (id === state.sessionId && !state.isPending) {
      closeDrawer();
      return;
    }
    state.abort?.abort();
    resetLiveState();
    state.messages = [];
    setSession(id);
    renderSidebar(); // active 강조 즉시 반영
    loadSession();
    closeDrawer();
    $input.focus();
  }

  async function deleteConversation(id, title) {
    const label = (title || "").trim() || "이 대화";
    if (!confirm(`"${label}" 대화를 삭제할까요?`)) return;
    try {
      const res = await fetch(`${API_BASE}/conversations/${id}`, {
        method: "DELETE",
      });
      if (!res.ok && res.status !== 404) return;
    } catch (e) {
      console.error(e);
      return;
    }
    // 삭제한 대화가 현재 열려 있던 세션이면 새 채팅 상태로 전환.
    if (id === state.sessionId) {
      resetLiveState();
      state.messages = [];
      setSession(null);
      render();
    }
    await loadConversations();
  }

  // new-chat / switchSession / delete 가 공유하는 라이브 메타 초기화.
  function resetLiveState() {
    state.pendingUser = null;
    state.streamingAnswer = "";
    state.liveSources = null;
    state.liveSuggestions = [];
    state.liveLatency = undefined;
    $error.dataset.msg = "";
  }

  // ───────────────── 렌더 ─────────────────
  // 한 번에 전체를 다시 그린다. 메시지 수가 많지 않아 비용보다 단순성이 이득.
  // display 배열 = 영속 메시지(state.messages) + 옵티미스틱 user + 스트리밍 assistant.
  function render() {
    const hasContent =
      state.messages.length > 0 ||
      state.pendingUser !== null ||
      state.streamingAnswer.length > 0;
    $empty.classList.toggle("hidden", hasContent);

    // 마지막 assistant 메시지에 한해 라이브 메타(sources/suggestions/latency)를 머지.
    // 스트리밍이 끝난 직후 loadSession() 이 messages 를 다시 채우는데, 그 시점에도
    // 동일 인덱스의 assistant 버블에 메타가 자연스럽게 붙도록 하기 위함.
    const display = state.messages.map((m, i) => {
      if (
        i === state.messages.length - 1 &&
        m.role === "assistant" &&
        (state.liveSources ||
          state.liveSuggestions.length ||
          state.liveLatency !== undefined)
      ) {
        return {
          ...m,
          sources: state.liveSources ?? m.sources,
          suggestions:
            state.liveSuggestions.length
              ? state.liveSuggestions
              : m.suggestions,
          latency_ms: state.liveLatency ?? m.latency_ms,
        };
      }
      return m;
    });

    // pendingUser 가 이미 messages 의 마지막 user 와 동일하면 중복 표시 회피
    // — loadSession() 직후엔 서버가 user 메시지를 확정해서 돌려주기 때문.
    const lastBaseUser = (() => {
      for (let i = state.messages.length - 1; i >= 0; i--) {
        if (state.messages[i].role === "user") return state.messages[i].content;
      }
      return null;
    })();

    if (state.pendingUser && lastBaseUser !== state.pendingUser) {
      display.push({ role: "user", content: state.pendingUser });
    }
    // 스트리밍 중인 가상 assistant 버블. streaming 플래그가 caret(깜빡이) 클래스를 켠다.
    if (state.streamingAnswer) {
      display.push({
        role: "assistant",
        content: state.streamingAnswer,
        sources: state.liveSources ?? undefined,
        streaming: true,
      });
    }

    $messages.innerHTML = "";
    display.forEach((m) => $messages.appendChild(renderBubble(m)));

    // 후속 질문 칩은 스트림 종료(=isPending false)일 때만 보여준다.
    // 스트리밍 중에는 답변이 아직 자라는 중이라 칩이 깜빡일 수 있어 의도적으로 숨김.
    const lastIdx = display.length - 1;
    const last = display[lastIdx];
    if (
      !state.isPending &&
      last &&
      last.role === "assistant" &&
      last.suggestions &&
      last.suggestions.length
    ) {
      $messages.appendChild(renderSuggestions(last.suggestions));
    }

    // "생각 중…" 상태바: 보낸 직후 ~ 첫 토큰 도착 전 사이에만 보이도록.
    $status.classList.toggle(
      "hidden",
      !state.isPending || !!state.streamingAnswer,
    );
    $error.classList.toggle("hidden", !$error.dataset.msg);
    if ($error.dataset.msg) $error.textContent = `오류: ${$error.dataset.msg}`;

    // 입력 영역 상태: 전송/중지 버튼은 진행 여부에 따라 상호 배타적.
    $send.disabled = state.isPending || !$input.value.trim();
    $send.classList.toggle("hidden", state.isPending);
    $cancel.classList.toggle("hidden", !state.isPending);
  }

  function renderBubble(m) {
    const wrap = document.createElement("div");
    // user 는 오른쪽 정렬, assistant 는 전폭 — Tailwind 유틸리티 클래스 조합.
    wrap.className = m.role === "user" ? "flex justify-end" : "";

    const inner = document.createElement("div");
    inner.className = "max-w-[85%]" + (m.role === "user" ? "" : " w-full");

    const bubble = document.createElement("div");
    bubble.className =
      m.role === "user" ? "bubble-user" : "bubble-assistant";

    if (m.role === "user") {
      // 사용자 입력은 절대 마크다운으로 해석하지 않음 — XSS 표면을 줄이기 위해 textContent.
      bubble.textContent = m.content;
    } else {
      // 어시스턴트 본문만 마크다운 → DOMPurify → 하이라이트.
      const prose = document.createElement("div");
      prose.className = "prose max-w-none";
      prose.innerHTML = renderMarkdown(m.content);
      highlightWithin(prose);
      if (m.streaming) prose.classList.add("caret");
      bubble.appendChild(prose);
    }

    inner.appendChild(bubble);

    if (m.role === "assistant" && m.sources && m.sources.length) {
      inner.appendChild(renderSourceExpander(m.sources, m.latency_ms));
    }

    wrap.appendChild(inner);
    return wrap;
  }

  // 접이식 소스 카드 영역. 기본 접힘 상태로 두어 본문 가독성을 우선시한다.
  function renderSourceExpander(sources, latencyMs) {
    const container = document.createElement("div");
    container.className = "mt-1.5";

    const btn = document.createElement("button");
    btn.type = "button";
    btn.className =
      "flex items-center gap-1 text-xs text-brand-muted hover:text-brand-fg";
    btn.innerHTML = `
      <svg class="chev" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 9l6 6 6-6"/></svg>
      📎 소스 ${sources.length}개${
        typeof latencyMs === "number" ? ` · ${latencyMs}ms` : ""
      }`;

    const list = document.createElement("div");
    list.className = "mt-1.5 space-y-1.5 hidden";

    sources.forEach((s) => {
      const card = document.createElement("div");
      card.className = "source-card bg-white";

      const headRow = document.createElement("div");
      headRow.className = "flex items-center gap-1.5 text-xs";

      // content_type 에 따른 아이콘 — 백엔드 ContentType: text/table/image.
      const icon = document.createElement("span");
      icon.textContent =
        s.content_type === "table"
          ? "▦"
          : s.content_type === "image"
            ? "🖼"
            : "📄";
      icon.className = "text-brand-muted";
      headRow.appendChild(icon);

      const title = document.createElement("span");
      title.className = "font-medium truncate flex-1";
      title.textContent = s.title || s.doc_id || "(제목 없음)";
      headRow.appendChild(title);

      // page 가 0 일 수도 있어서 truthy 가 아니라 typeof 검사.
      if (typeof s.page === "number") {
        const page = document.createElement("span");
        page.className = "badge badge-outline";
        page.textContent = `p.${s.page}`;
        headRow.appendChild(page);
      }

      const score = document.createElement("span");
      score.className = "badge";
      // 점수가 null/undefined 인 케이스(예: BM25 단독 fallback)도 0 으로 안전 표시.
      score.textContent = (s.score ?? 0).toFixed(3);
      headRow.appendChild(score);

      const excerpt = document.createElement("p");
      excerpt.className = "mt-1 text-xs text-brand-muted source-excerpt";
      excerpt.textContent = s.excerpt || "";

      card.appendChild(headRow);
      card.appendChild(excerpt);
      list.appendChild(card);
    });

    btn.addEventListener("click", () => {
      // toggle() 의 반환값(있음=true)을 뒤집어 "열렸는가" 로 사용.
      const open = list.classList.toggle("hidden") === false;
      btn.querySelector(".chev").classList.toggle("open", open);
    });

    container.appendChild(btn);
    container.appendChild(list);
    return container;
  }

  // 후속 질문 칩 — 클릭하면 해당 질문을 즉시 sendMessage() 로 전송.
  function renderSuggestions(items) {
    const wrap = document.createElement("div");
    wrap.className = "mt-3 flex flex-wrap gap-2";
    items.forEach((q) => {
      const chip = document.createElement("button");
      chip.type = "button";
      chip.className =
        "text-xs px-3 py-1.5 rounded-full border border-brand-border bg-white hover:bg-brand-accent transition text-brand-fg";
      chip.textContent = q;
      chip.addEventListener("click", () => sendMessage(q));
      wrap.appendChild(chip);
    });
    return wrap;
  }

  // ───────────────── 스크롤 ─────────────────
  // sticky=true 인 동안만 새 토큰마다 바닥으로 끌어내린다.
  // requestAnimationFrame 으로 한 프레임 미뤄야 직전 render() 가 반영된 후의 scrollHeight 를 읽는다.
  function scrollToBottom(force = false) {
    if (!force && !state.sticky) return;
    requestAnimationFrame(() => {
      $scroll.scrollTop = $scroll.scrollHeight;
    });
  }
  // 사용자가 위로 120px 이상 올리면 sticky 해제 — 과거 메시지를 읽는 중에 끌어내리지 않기 위함.
  $scroll.addEventListener("scroll", () => {
    const dist = $scroll.scrollHeight - $scroll.clientHeight - $scroll.scrollTop;
    state.sticky = dist < 120;
  });

  // ───────────────── SSE 스트림 ─────────────────
  // fetch + ReadableStream 을 직접 파싱하는 이유:
  //   · 표준 EventSource 는 POST 와 커스텀 헤더를 지원하지 않음.
  //   · AbortController 로 사용자 중지(/새 채팅) 시 즉시 끊을 수 있어야 함.
  // 프레임 구분: SSE 규약상 빈 줄("\n\n") 이 한 이벤트의 끝.
  async function streamQuery(req) {
    const controller = new AbortController();
    state.abort = controller;
    state.isPending = true;
    $error.dataset.msg = "";
    render();

    try {
      const res = await fetch(`${API_BASE}/query/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(req),
        signal: controller.signal,
      });
      if (!res.ok || !res.body) {
        // 본문이 텍스트면 그대로, 아니면 statusText 라도 노출.
        const t = await res.text().catch(() => res.statusText);
        $error.dataset.msg = t || `HTTP ${res.status}`;
        return;
      }

      // TextDecoderStream 으로 바이트→문자열 변환을 위임 (UTF-8 멀티바이트 경계 안전).
      const reader = res.body.pipeThrough(new TextDecoderStream()).getReader();
      let buffer = "";      // 아직 "\n\n" 을 만나지 못한 잔여 텍스트
      let accumulated = ""; // 지금까지 누적된 토큰(=어시스턴트 본문)

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += value;

        // 한 번의 read() 안에 여러 SSE 이벤트가 들어올 수 있으므로 while 로 모두 소진.
        let idx;
        while ((idx = buffer.indexOf("\n\n")) !== -1) {
          const raw = buffer.slice(0, idx);
          buffer = buffer.slice(idx + 2);

          // 한 이벤트 안에서 "data:" 가 여러 줄에 걸쳐 올 수 있어 배열로 모은 뒤 join.
          let event = "message";
          const dataLines = [];
          for (const line of raw.split("\n")) {
            if (line.startsWith("event:")) event = line.slice(6).trim();
            else if (line.startsWith("data:"))
              // 표준상 "data: " 의 첫 공백 한 칸만 트림(데이터 자체의 공백은 보존).
              dataLines.push(line.slice(5).replace(/^ /, ""));
          }
          if (!dataLines.length) continue;

          // 백엔드는 모든 데이터를 JSON 으로 보냄. 깨진 프레임은 그냥 스킵.
          let data;
          try {
            data = JSON.parse(dataLines.join("\n"));
          } catch {
            continue;
          }

          switch (event) {
            case "meta":
              // 첫 응답에서 서버가 세션을 새로 만들어 돌려주는 경우 URL/localStorage 갱신.
              if (data.session_id && data.session_id !== state.sessionId) {
                setSession(data.session_id);
              }
              break;
            case "sources":
              // 토큰보다 먼저 도착하기도 함 — 본문 렌더 전부터 소스 카드 보일 수 있도록 즉시 반영.
              state.liveSources = data;
              render();
              break;
            case "token":
              // 토큰은 문자열로 도착. 안전상 string 인지 확인 후 누적.
              if (typeof data === "string") {
                accumulated += data;
                state.streamingAnswer = accumulated;
                render();
                scrollToBottom();
              }
              break;
            case "suggestions":
              // 칩은 스트림 종료 후에만 그리지만, 마지막 done 이벤트 전에 미리 받아둠.
              state.liveSuggestions = Array.isArray(data) ? data : [];
              break;
            case "done":
              state.liveLatency = data?.latency_ms;
              break;
            case "error":
              $error.dataset.msg = data?.message || "스트림 오류";
              break;
          }
        }
      }

      // 스트림이 정상 종료되면 서버에 영속화된 메시지를 재조회해서 messages 와 싱크.
      // 이렇게 하면 토큰 누적본과 서버의 최종본(예: 마크다운 후처리 차이) 사이의 미세한 어긋남이 사라지고,
      // 다음 질문 시점에 일관된 conversation 컨텍스트가 보장된다.
      await loadSession();
      state.streamingAnswer = "";
      state.pendingUser = null;
      render();
      // 새 세션 생성/제목 자동 설정/updated_at 변동을 사이드바에 반영.
      loadConversations();
    } catch (e) {
      // 사용자가 명시적으로 중지(abort)한 경우는 오류 메시지를 띄우지 않는다.
      if (e.name !== "AbortError") {
        $error.dataset.msg = e.message || String(e);
      }
    } finally {
      state.isPending = false;
      state.abort = null;
      render();
      scrollToBottom();
    }
  }

  // ───────────────── 입력 ─────────────────
  // text 인자가 있으면 칩에서 직접 보낸 것, 없으면 textarea 의 현재 값.
  function sendMessage(text) {
    const q = (text ?? $input.value).trim();
    if (!q || state.isPending) return;

    // 새 질문 시 라이브 메타를 모두 비워서 이전 답변의 칩/소스가 잠깐이라도 뒤섞이지 않도록 초기화.
    state.pendingUser = q;
    state.streamingAnswer = "";
    state.liveSources = null;
    state.liveSuggestions = [];
    state.liveLatency = undefined;
    $input.value = "";
    autosize();
    // 새 질문 시점에는 항상 바닥으로 — 사용자가 보낸 직후엔 답을 보려고 한다는 가정.
    state.sticky = true;
    render();
    scrollToBottom(true);

    streamQuery({
      question: q,
      session_id: state.sessionId,
    });
  }

  // textarea 높이를 내용에 맞추되 최대 200px 로 제한 (그 이상은 내부 스크롤).
  function autosize() {
    $input.style.height = "auto";
    $input.style.height = Math.min($input.scrollHeight, 200) + "px";
    $send.disabled = state.isPending || !$input.value.trim();
  }

  $input.addEventListener("input", autosize);
  $input.addEventListener("keydown", (e) => {
    // Enter 전송 / Shift+Enter 줄바꿈.
    // isComposing 체크는 한글/일본어 IME 조합 중인 Enter 가 잘못 전송되는 것을 막기 위함.
    if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
      e.preventDefault();
      sendMessage();
    }
  });
  $form.addEventListener("submit", (e) => {
    e.preventDefault();
    sendMessage();
  });
  // 중지 버튼: 진행 중인 fetch 를 abort. streamQuery 의 finally 가 상태를 정리한다.
  $cancel.addEventListener("click", () => {
    state.abort?.abort();
  });
  // 새 채팅: 진행 중인 스트림을 끊고 모든 라이브/영속 상태 초기화.
  $newChat.addEventListener("click", () => {
    state.abort?.abort();
    resetLiveState();
    state.messages = [];
    setSession(null);
    render();
    renderSidebar(); // active 강조 해제
    closeDrawer();
    $input.focus();
  });

  // ───────────────── 리사이저 / 접기 / 드로어 ─────────────────
  // 사이드바 폭은 --sidebar-w CSS 변수 하나로만 제어하고, 값은 localStorage 에 영속화.
  const SIDEBAR_KEY = "sidebar_width";
  const SIDEBAR_COLLAPSE_KEY = "sidebar_collapsed";
  const SIDEBAR_MIN = 200;
  const SIDEBAR_MAX = 480;
  const SIDEBAR_DEFAULT = 280;

  function isMobile() {
    return window.matchMedia("(max-width: 768px)").matches;
  }

  // 폭을 [MIN, MAX] 로 클램프해 적용하고 적용된 정수 폭을 반환.
  function setSidebarWidth(px) {
    const w = Math.round(Math.min(SIDEBAR_MAX, Math.max(SIDEBAR_MIN, px)));
    $app.style.setProperty("--sidebar-w", w + "px");
    return w;
  }
  function currentWidth() {
    const v = parseInt(
      getComputedStyle($app).getPropertyValue("--sidebar-w"),
      10,
    );
    return Number.isNaN(v) ? SIDEBAR_DEFAULT : v;
  }

  // 드래그: clientX 가 곧 사이드바 폭(사이드바 좌측이 viewport left=0 에서 시작).
  $resizer.addEventListener("mousedown", (e) => {
    if (isMobile()) return;
    e.preventDefault();
    $app.classList.add("resizing");
    let applied = currentWidth();
    const onMove = (ev) => {
      applied = setSidebarWidth(ev.clientX);
    };
    const onUp = () => {
      $app.classList.remove("resizing");
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup", onUp);
      localStorage.setItem(SIDEBAR_KEY, String(applied));
    };
    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
  });

  // 더블클릭으로 기본 폭 복원.
  $resizer.addEventListener("dblclick", () => {
    localStorage.setItem(SIDEBAR_KEY, String(setSidebarWidth(SIDEBAR_DEFAULT)));
  });

  // 키보드 접근성: 리사이저에 포커스 후 ←/→ 로 16px 씩 조절.
  $resizer.addEventListener("keydown", (e) => {
    if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
    e.preventDefault();
    const step = e.key === "ArrowRight" ? 16 : -16;
    localStorage.setItem(
      SIDEBAR_KEY,
      String(setSidebarWidth(currentWidth() + step)),
    );
  });

  function openDrawer() {
    $app.classList.add("drawer-open");
    $backdrop.classList.remove("hidden");
  }
  function closeDrawer() {
    $app.classList.remove("drawer-open");
    $backdrop.classList.add("hidden");
  }

  // 토글 버튼: 모바일=드로어 열고닫기, 데스크톱=사이드바 접기.
  $sidebarToggle.addEventListener("click", () => {
    if (isMobile()) {
      $app.classList.contains("drawer-open") ? closeDrawer() : openDrawer();
    } else {
      $app.classList.toggle("collapsed");
      localStorage.setItem(
        SIDEBAR_COLLAPSE_KEY,
        $app.classList.contains("collapsed") ? "1" : "0",
      );
    }
  });
  $backdrop.addEventListener("click", closeDrawer);

  // 저장된 폭 / 접힘 상태 복원.
  const savedWidth = parseInt(localStorage.getItem(SIDEBAR_KEY) || "", 10);
  if (!Number.isNaN(savedWidth)) setSidebarWidth(savedWidth);
  if (localStorage.getItem(SIDEBAR_COLLAPSE_KEY) === "1" && !isMobile()) {
    $app.classList.add("collapsed");
  }

  // ───────────────── 초기화 ─────────────────
  // 1) URL 동기화로 헤더 pill 먼저 표시 → 2) 세션이 있으면 비동기로 메시지 로드
  // → 3) textarea 높이 보정 → 4) 입력 포커스.
  syncSessionUrl();
  loadSession();
  loadConversations();
  autosize();
  $input.focus();
})();
