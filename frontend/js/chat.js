/**
 * GPT 风格对话：左侧历史、右侧消息流
 */
(function () {
  const STORAGE_KEY = "kg_nexus_chat_sessions";

  let sessions = [];
  let activeId = null;

  function uid() {
    return `chat_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`;
  }

  function loadSessions() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      sessions = raw ? JSON.parse(raw) : [];
    } catch {
      sessions = [];
    }
    if (!sessions.length) {
      const s = createSessionData();
      sessions.push(s);
      activeId = s.id;
      saveSessions();
    } else if (!activeId || !sessions.find((s) => s.id === activeId)) {
      activeId = sessions[0].id;
    }
  }

  function saveSessions() {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(sessions));
    } catch (e) {
      console.warn("无法保存对话记录", e);
    }
  }

  function createSessionData(title = "新对话") {
    return {
      id: uid(),
      title,
      messages: [],
      createdAt: Date.now(),
      updatedAt: Date.now(),
    };
  }

  function getActiveSession() {
    return sessions.find((s) => s.id === activeId);
  }

  function sessionPreview(session) {
    if (session.messages.length) {
      const first = session.messages.find((m) => m.role === "user");
      if (first) return first.content.slice(0, 28);
    }
    return session.title || "新对话";
  }

  function formatTime(ts) {
    const d = new Date(ts);
    const now = new Date();
    if (d.toDateString() === now.toDateString()) {
      return d.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
    }
    return d.toLocaleDateString("zh-CN", { month: "short", day: "numeric" });
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function renderHistoryList() {
    const list = document.getElementById("chatHistoryList");
    if (!list) return;

    const sorted = [...sessions].sort((a, b) => b.updatedAt - a.updatedAt);
    list.innerHTML = sorted
      .map(
        (s) => `
      <li class="chat-history-item${s.id === activeId ? " active" : ""}">
        <div class="chat-history-row">
          <button type="button" class="chat-history-btn" data-id="${escapeHtml(s.id)}">
            <span class="chat-history-title">${escapeHtml(sessionPreview(s))}</span>
            <span class="chat-history-meta">${formatTime(s.updatedAt)} · ${s.messages.length} 条</span>
          </button>
          <button
            type="button"
            class="chat-history-delete"
            data-id="${escapeHtml(s.id)}"
            aria-label="删除此对话"
            title="删除此对话"
          >×</button>
        </div>
      </li>`
      )
      .join("");

    list.querySelectorAll(".chat-history-btn").forEach((btn) => {
      btn.addEventListener("click", () => switchSession(btn.dataset.id));
    });
    list.querySelectorAll(".chat-history-delete").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        deleteSession(btn.dataset.id);
      });
    });
  }

  function renderMessages() {
    const container = document.getElementById("chatMessages");
    const titleEl = document.getElementById("chatSessionTitle");
    const session = getActiveSession();
    if (!container || !session) return;

    if (titleEl) titleEl.textContent = sessionPreview(session);

    if (!session.messages.length) {
      container.innerHTML = `
        <div class="chat-welcome">
          <p>你好，我是 KG Nexus 助手。</p>
          <p>输入问题探索中国先进 AI 知识图谱，回答将同步高亮图谱中的相关实体。</p>
          <div class="chip-row chat-suggestions">
            <button type="button" class="chip chat-suggest" data-q="深度学习属于什么技术领域？">深度学习</button>
            <button type="button" class="chip chat-suggest" data-q="文心一言是什么？">文心一言</button>
            <button type="button" class="chip chat-suggest" data-q="百度研发了哪些AI产品？">百度产品</button>
          </div>
        </div>`;
      bindSuggestChips(container);
      return;
    }

    container.innerHTML = session.messages
      .map((m) => {
        if (m.role === "user") {
          return `
          <div class="chat-bubble chat-bubble--user">
            <span class="chat-avatar">我</span>
            <div class="chat-bubble-body">${escapeHtml(m.content)}</div>
          </div>`;
        }
        const meta = m.meta || {};
        const pills = [
          meta.intent ? `<span class="pill">${escapeHtml(meta.intent)}</span>` : "",
          meta.entity ? `<span class="pill">${escapeHtml(meta.entity)}</span>` : "",
          meta.confidence != null
            ? `<span class="pill pill-accent">${Math.round(meta.confidence * 100)}%</span>`
            : "",
          meta.mode ? `<span class="pill">${escapeHtml(meta.mode)}</span>` : "",
        ]
          .filter(Boolean)
          .join("");
        const evidence = meta.evidence
          ? `<div class="qa-evidence" style="margin-top:0.5rem;font-size:0.75rem;color:var(--text-muted)">${escapeHtml(meta.evidence)}</div>`
          : "";
        return `
        <div class="chat-bubble chat-bubble--assistant">
          <span class="chat-avatar">KG</span>
          <div>
            <div class="chat-bubble-body">${escapeHtml(m.content)}</div>
            ${pills ? `<div class="chat-bubble-meta">${pills}</div>` : ""}
            ${evidence}
          </div>
        </div>`;
      })
      .join("");

    container.scrollTop = container.scrollHeight;
  }

  function bindSuggestChips(root) {
    root.querySelectorAll(".chat-suggest").forEach((btn) => {
      btn.addEventListener("click", () => {
        const q = btn.dataset.q;
        const input = document.getElementById("chatInput");
        if (input && q) {
          input.value = q;
          sendMessage();
        }
      });
    });
  }

  function switchSession(id) {
    activeId = id;
    saveSessions();
    renderHistoryList();
    renderMessages();
  }

  function newSession() {
    const s = createSessionData();
    sessions.unshift(s);
    activeId = s.id;
    saveSessions();
    renderHistoryList();
    renderMessages();
  }

  function deleteSession(id) {
    const session = sessions.find((s) => s.id === id);
    if (!session) return;

    if (session.messages.length) {
      const preview = sessionPreview(session);
      if (!confirm(`确定删除「${preview}」？删除后无法恢复。`)) return;
    }

    sessions = sessions.filter((s) => s.id !== id);

    if (!sessions.length) {
      const s = createSessionData();
      sessions.push(s);
      activeId = s.id;
    } else if (activeId === id) {
      const sorted = [...sessions].sort((a, b) => b.updatedAt - a.updatedAt);
      activeId = sorted[0].id;
    }

    saveSessions();
    renderHistoryList();
    renderMessages();
  }

  function clearAllSessions() {
    const hasContent = sessions.some((s) => s.messages.length > 0);
    if (hasContent && !confirm("确定清空全部对话记录？删除后无法恢复。")) return;

    const s = createSessionData();
    sessions = [s];
    activeId = s.id;
    saveSessions();
    renderHistoryList();
    renderMessages();
  }

  function appendMessage(role, content, meta = null) {
    const session = getActiveSession();
    if (!session) return;
    session.messages.push({ role, content, meta, ts: Date.now() });
    session.updatedAt = Date.now();
    if (role === "user" && session.messages.filter((m) => m.role === "user").length === 1) {
      session.title = content.slice(0, 24) + (content.length > 24 ? "…" : "");
    }
    saveSessions();
    renderHistoryList();
    renderMessages();
  }

  function showTyping() {
    const container = document.getElementById("chatMessages");
    if (!container) return;
    const el = document.createElement("div");
    el.id = "chatTyping";
    el.className = "chat-bubble chat-bubble--assistant chat-bubble--typing";
    el.innerHTML = `
      <span class="chat-avatar">KG</span>
      <div class="chat-bubble-body">正在思考…</div>`;
    container.appendChild(el);
    container.scrollTop = container.scrollHeight;
  }

  function hideTyping() {
    document.getElementById("chatTyping")?.remove();
  }

  async function sendMessage() {
    const input = document.getElementById("chatInput");
    const btn = document.getElementById("btnSendChat");
    const text = input?.value.trim();
    if (!text || !window.KGApp) return;

    input.value = "";
    input.style.height = "auto";
    appendMessage("user", text);

    btn.disabled = true;
    showTyping();

    try {
      const mode = document.getElementById("qaMode")?.value || "kg";
      // 先展示问答结果，图谱同步放后台，避免长时间停在「正在思考…」
      const result = await window.KGApp.fetchAnswer(text, mode);

      hideTyping();

      const questionKeywords =
        result.matched_entities?.length > 0
          ? result.matched_entities
          : await window.KGApp.matchEntitiesInText(text);
      const related = window.KGApp.filterKnownEntityNames(result.evidence || []);

      const legendParts = [];
      if (questionKeywords.length) legendParts.push(`问句实体：${questionKeywords.join("、")}`);
      if (related.length) legendParts.push(`答案关联：${related.join("、")}`);

      const evidenceText =
        (result.evidence?.length ? `证据：${result.evidence.join(" · ")}` : "") +
        (legendParts.length ? ` · ${legendParts.join(" · ")}` : "");

      appendMessage("assistant", result.answer, {
        intent: result.intent,
        entity: result.entity || "—",
        confidence: result.confidence,
        mode: result.mode,
        evidence: evidenceText,
      });

      window.KGApp.syncGraphFromAnswer(text, result).catch((syncErr) => {
        console.warn("图谱同步失败", syncErr);
      });
    } catch (err) {
      hideTyping();
      appendMessage("assistant", `抱歉，请求失败：${err.message}`);
    } finally {
      btn.disabled = false;
      input?.focus();
    }
  }

  function bindChatEvents() {
    document.getElementById("btnNewChat")?.addEventListener("click", newSession);
    document.getElementById("btnClearAllChats")?.addEventListener("click", clearAllSessions);
    document.getElementById("btnSendChat")?.addEventListener("click", sendMessage);

    const input = document.getElementById("chatInput");
    input?.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
      }
    });

    input?.addEventListener("input", () => {
      input.style.height = "auto";
      input.style.height = `${Math.min(input.scrollHeight, 160)}px`;
    });
  }

  function initChat() {
    loadSessions();
    renderHistoryList();
    renderMessages();
    bindChatEvents();
  }

  window.initChat = initChat;
})();
