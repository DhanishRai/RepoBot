let currentRepo = '';
let chatHistory = [];

const $ = (id) => document.getElementById(id);
const markdown = (value) => DOMPurify.sanitize(marked.parse(value || ''));

function setStatus(message, isError = false) {
  const status = $('statusMessage');
  status.textContent = message;
  status.classList.toggle('text-red-300', isError);
  status.classList.toggle('text-tokyo-muted', !isError);
}

async function requestJson(url, body) {
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.detail || `Request failed (${response.status}).`);
  return payload;
}

function renderStats(stats) {
  const container = $('repoStats');
  container.replaceChildren();
  [[`★ ${Number(stats.stars || 0).toLocaleString()} stars`, 'text-tokyo-accent'],
    [`⑂ ${Number(stats.forks || 0).toLocaleString()} forks`, 'text-tokyo-green'],
    [stats.language || 'Not detected', 'text-tokyo-text']].forEach(([label, color]) => {
    const badge = document.createElement('span');
    badge.className = `rounded-full bg-[#24283b] px-3 py-1 ${color}`;
    badge.textContent = label;
    container.appendChild(badge);
  });
  container.classList.remove('hidden');
  container.classList.add('flex');
}

function renderTree(items, stats) {
  const list = $('fileTree');
  list.replaceChildren();
  const baseUrl = new URL(stats.url);
  items.forEach(({ path, type }) => {
    const item = document.createElement('li');
    const link = document.createElement('a');
    const encodedPath = path.split('/').map(encodeURIComponent).join('/');
    link.href = `${baseUrl.origin}/${baseUrl.pathname.split('/').filter(Boolean).slice(0, 2).join('/')}/blob/${encodeURIComponent(stats.default_branch)}/${encodedPath}`;
    link.target = '_blank';
    link.rel = 'noopener noreferrer';
    link.textContent = `${type === 'tree' ? '▸ ' : '· '}${path}`;
    item.appendChild(link);
    list.appendChild(item);
  });
  $('treeDetails').classList.toggle('hidden', items.length === 0);
  $('treeNote').textContent = items.length ? `${items.length} paths shown${$('treeDetails').dataset.truncated === 'true' ? ' (repository tree is larger)' : ''}.` : 'No files found.';
}

async function analyzeRepo() {
  const repoUrl = $('repoUrl').value.trim();
  if (!repoUrl) {
    setStatus('Enter a public GitHub repository URL first.', true);
    $('repoUrl').focus();
    return;
  }
  const button = $('analyzeButton');
  button.disabled = true;
  button.textContent = 'Analyzing…';
  setStatus('Fetching repository metadata and project files…');
  try {
    const payload = await requestJson('/api/inspect', { repo_url: repoUrl });
    currentRepo = repoUrl;
    chatHistory = [];
    $('repoName').textContent = payload.stats.name;
    renderStats(payload.stats);
    $('blueprint').innerHTML = markdown(payload.blueprint);
    $('treeDetails').dataset.truncated = String(payload.tree_truncated);
    renderTree(payload.tree || [], payload.stats);
    $('chatMessages').replaceChildren();
    appendMessage('bot', 'Repository loaded. Ask about its setup, dependencies, files, or automation.');
    $('sendButton').disabled = false;
    $('questionInput').disabled = false;
    $('questionInput').focus();
    setStatus(payload.cached ? 'Loaded from this session’s cache.' : 'Analysis complete.');
  } catch (error) {
    setStatus(error.message, true);
  } finally {
    button.disabled = false;
    button.textContent = 'Analyze';
  }
}

function appendMessage(role, content, elementId) {
  const node = document.createElement('div');
  if (elementId) node.id = elementId;
  node.className = role === 'user'
    ? 'ml-auto max-w-[90%] rounded-lg bg-tokyo-accent p-4 text-sm leading-6 text-[#16161e]'
    : 'max-w-[90%] rounded-lg border border-[#3b4261] bg-tokyo-input p-4 text-sm leading-6 text-tokyo-text';
  if (role === 'user') node.textContent = content;
  else node.innerHTML = markdown(content);
  $('chatMessages').appendChild(node);
  $('chatMessages').scrollTop = $('chatMessages').scrollHeight;
  return node;
}

async function sendQuestion() {
  const input = $('questionInput');
  const question = input.value.trim();
  if (!question || !currentRepo) return;
  input.value = '';
  appendMessage('user', question);
  const thinking = appendMessage('bot', 'Thinking…', 'thinking');
  $('sendButton').disabled = true;
  try {
    const payload = await requestJson('/api/chat', { repo_url: currentRepo, question, history: chatHistory });
    thinking.innerHTML = markdown(payload.answer);
    chatHistory.push({ role: 'user', content: question }, { role: 'model', content: payload.answer });
  } catch (error) {
    thinking.textContent = error.message;
    thinking.classList.add('text-red-300');
  } finally {
    $('sendButton').disabled = false;
    $('chatMessages').scrollTop = $('chatMessages').scrollHeight;
    input.focus();
  }
}

$('analyzeButton').addEventListener('click', analyzeRepo);
$('sendButton').addEventListener('click', sendQuestion);
$('repoUrl').addEventListener('keydown', (event) => {
  if (event.key === 'Enter') analyzeRepo();
});
$('questionInput').addEventListener('keydown', (event) => {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault();
    sendQuestion();
  }
});