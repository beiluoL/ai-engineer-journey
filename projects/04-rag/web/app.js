/* 零构建前端：原生 JS。全部逻辑约 200 行 —— 一个知识库助手不需要工程化，
   而「不需要工程化」本身就是这个项目的产品选择之一（离线可跑、拷走就能用）。

   状态只有 4 个，都放在 `state` 里：当前会话、会话列表、是否生成中、中止信号。
*/

const state = {
  sessionId: null,     // 当前会话；null = 还没建过（首次提问时才懒创建）
  sessions: [],        // 列表页数据
  busy: false,
  controller: null,    // AbortController：中止正在生成的那一轮
};

const $ = (id) => document.getElementById(id);
const messagesEl = $('messages');
const inputEl = $('input');
const errorEl = $('error');
const sendBtn = $('send');
const stopBtn = $('stop');
const listEl = $('session-list');

/* ---------- 会话列表 ---------- */

async function loadSessions() {
  try {
    const res = await fetch('/sessions');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    state.sessions = await res.json();
  } catch (e) {
    setError(`会话列表加载失败：${e.message}`);
  }
  renderList();
}

function renderList() {
  listEl.innerHTML = '';
  for (const s of state.sessions) {
    const li = document.createElement('li');
    li.className = 'session-item' + (s.id === state.sessionId ? ' active' : '');

    const title = document.createElement('span');
    title.className = 'session-title';
    title.textContent = s.title;
    title.title = '点击加载这个会话';
    title.onclick = () => openSession(s.id);

    const meta = document.createElement('span');
    meta.className = 'session-meta';
    meta.textContent = `${s.turn_count} 轮`;

    const actions = document.createElement('span');
    actions.className = 'row-actions';
    const rename = document.createElement('button');
    rename.className = 'mini';
    rename.textContent = '改名';
    rename.onclick = (ev) => { ev.stopPropagation(); renameSession(s.id, title); };
    const del = document.createElement('button');
    del.className = 'mini';
    del.textContent = '删除';
    del.onclick = (ev) => { ev.stopPropagation(); deleteSession(s.id, title); };
    actions.append(rename, del);

    li.append(title, meta, actions);
    listEl.appendChild(li);
  }
}

async function openSession(id) {
  state.sessionId = id;
  messagesEl.innerHTML = '';
  const detail = await fetch(`/sessions/${id}`).then((r) => r.json());
  for (const t of detail.turns) {
    appendTurn(t.role, t.content, t.sources, { refused: t.refused });
  }
  scrollBottom();
  await loadSessions();
}

async function createSession() {
  const res = await fetch('/sessions', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title: '新对话' }),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  state.sessionId = (await res.json()).id;
  messagesEl.innerHTML = '';
  await loadSessions();
}

async function renameSession(id, titleEl) {
  const title = prompt('新标题', titleEl.textContent || '');
  if (!title) return;
  const res = await fetch(`/sessions/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title }),
  });
  if (!res.ok) return setError(`改名失败：HTTP ${res.status}`);
  await loadSessions();
}

async function deleteSession(id, titleEl) {
  if (!confirm(`删除会话「${titleEl.textContent}」？此操作不可恢复。`)) return;
  const res = await fetch(`/sessions/${id}`, { method: 'DELETE' });
  if (!res.ok) return setError(`删除失败：HTTP ${res.status}`);
  if (state.sessionId === id) state.sessionId = null;
  messagesEl.innerHTML = '';
  await loadSessions();
}

/* ---------- 消息渲染 ---------- */

function buildSources(sources) {
  if (!sources || !sources.length) return null;
  const box = document.createElement('details');
  box.className = 'sources';
  box.open = true;
  const summary = document.createElement('summary');
  summary.textContent = `引用来源（${sources.length}）`;
  box.appendChild(summary);
  const ul = document.createElement('ul');
  for (const s of sources) {
    const li = document.createElement('li');
    li.textContent = s;
    ul.appendChild(li);
  }
  box.appendChild(ul);
  return box;
}

function appendTurn(role, text, sources, opts = {}) {
  const wrap = document.createElement('div');
  wrap.className = 'msg ' + role;

  const body = document.createElement('div');
  body.className = 'bubble' + (opts.refused ? ' refused' : '');
  body.textContent = text;
  wrap.appendChild(body);

  const src = buildSources(sources);
  if (src) wrap.appendChild(src);

  messagesEl.appendChild(wrap);
  scrollBottom();
  return { wrap, body, sources: src };
}

function scrollBottom() {
  const box = document.querySelector('.messages');
  if (box) box.scrollTop = box.scrollHeight;
}

function setBusy(on) {
  state.busy = on;
  sendBtn.disabled = on;
  stopBtn.disabled = !on;
  $('conn').className = 'conn ' + (on ? 'busy' : 'online');
  $('conn-text').textContent = on ? '生成中' : '就绪';
}

function setError(msg) {
  errorEl.textContent = msg || '';
  if (msg) setTimeout(() => { errorEl.textContent = ''; }, 6000);
}

/* ---------- 提问（SSE） ---------- */

async function ask() {
  const query = inputEl.value.trim();
  if (!query || state.busy) return;
  if (!state.sessionId) await createSession();     // 懒创建：第一次提问才建会话

  errorEl.textContent = '';
  inputEl.value = '';
  appendTurn('user', query, []);
  const target = appendTurn('assistant', '', []);
  const caret = document.createElement('span');
  caret.className = 'cursor';
  target.body.appendChild(caret);
  setBusy(true);

  const controller = new AbortController();
  state.controller = controller;
  try {
    const res = await fetch('/ask/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, session_id: state.sessionId }),
      signal: controller.signal,
    });
    if (!res.ok) {
      const detail = await res.json().catch(() => ({}));
      throw new Error(detail.detail || `HTTP ${res.status}`);
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder('utf-8');
    let buf = '';                 // 跨 chunk 的半帧必须留在 buf：网络分包与消息边界无关
    let sources = [];
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      let sep;
      while ((sep = buf.indexOf('\n\n')) >= 0) {
        const rawFrame = buf.slice(0, sep);
        buf = buf.slice(sep + 2);
        const line = rawFrame.split('\n').find((l) => l.startsWith('data: '));
        if (!line) continue;
        const payload = line.slice(6).trim();
        if (payload === '[DONE]') break;
        const ev = JSON.parse(payload);          // 服务端保证是 UTF-8 JSON
        if (ev.kind === 'retrieved') {
          sources = ev.sources || [];
        } else if (ev.kind === 'delta') {
          caret.remove();
          target.body.textContent += ev.text;    // 只追加增量，不整块重渲染
          target.body.appendChild(caret);
          scrollBottom();
        } else if (ev.kind === 'done') {
          caret.remove();
          target.body.textContent = ev.answer || '（模型没有给出内容）';
          sources = ev.sources || sources;
          if (ev.refused) target.body.className = 'bubble refused';
        } else if (ev.kind === 'error') {
          throw new Error(ev.message || '生成失败');
        }
      }
    }
    caret.remove();
  } catch (e) {
    caret.remove();
    if (e.name === 'AbortError') setError('已中止（本轮内容未保存）');
    else setError(e.message || '请求失败');
  } finally {
    state.controller = null;
    setBusy(false);
    await loadSessions();            // 标题与轮数变了，列表要同步
  }
}

/* ---------- 事件绑定 ---------- */

sendBtn.onclick = ask;
stopBtn.onclick = () => state.controller && state.controller.abort();
inputEl.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); ask(); }
});
$('new-session').onclick = async () => {
  await createSession();
  setError('');
};

(async function boot() {
  $('conn').className = 'conn online';
  $('conn-text').textContent = '就绪';
  try {
    const stats = await fetch('/stats').then((r) => r.json());
    $('stats').textContent = `${stats.chunks} chunks · top_k=${stats.top_k}`;
  } catch (_) {
    $('stats').textContent = '服务未就绪';
  }
  await loadSessions();
  // 自动会话：URL 带 #auto 时自动打开最近更新的一条，方便截图/链接直接展示历史
  if (location.hash === '#auto' && state.sessions.length > 0) {
    await openSession(state.sessions[0].id);
  }
  inputEl.focus();
})();
