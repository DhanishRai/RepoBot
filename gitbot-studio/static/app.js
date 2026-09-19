let currentRepo = '';
let chatHistory = [];

const $ = (id) => document.getElementById(id);

function setBusy(button, busy, busyText, idleText) {
  button.disabled = busy;
  button.textContent = busy ? busyText : idleText;
}

function showError(message) {
  $('blueprint').innerHTML = `<p class="text-sm text-red-300">${message}</p>`;
}

async function analyzeRepo() {
  const repoUrl = $('repoUrl').value.trim();
  if (!repoUrl) return showError('Enter a public GitHub repository URL first.');
  const button = $('analyzeButton');
  setBusy(button, true, 'Analyzing...', 'Analyze');
  try {
    const response = await fetch('/api/inspect', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ repo_url: repoUrl }) });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || 'Inspection failed.');
    currentRepo = repoUrl;
    chatHistory = [];
    $('repoName').textContent = payload.stats.name;
    $('repoStats').innerHTML = `<span class="rounded-full bg-[#24283b] px-3 py-1 text-tokyo-accent">★ ${payload.stats.stars.toLocaleString()}</span><span class="rounded-full bg-[#24283b] px-3 py-1 text-tokyo-green">${payload.stats.language}</span>`;
    $('repoStats').classList.remove('hidden');
    $('repoStats').classList.add('flex');
    $('blueprint').innerHTML = marked.parse(payload.blueprint);
    $('chatMessages').innerHTML = '<div class="max-w-[90%] rounded-lg border border-[#3b4261] bg-tokyo-input p-4 text-sm leading-6 text-tokyo-text">Repository loaded. What would you like to understand?</div>';
  } catch (error) { showError(error.message); } finally { setBusy(button, false, 'Analyzing...', 'Analyze'); }
}

function appendMessage(role, content, elementId) {
  const node = document.createElement('div');
  node.id = elementId || '';
  node.className = role === 'user' ? 'ml-auto max-w-[90%] rounded-lg bg-tokyo-accent p-4 text-sm leading-6 text-[#16161e]' : 'max-w-[90%] rounded-lg border border-[#3b4261] bg-tokyo-input p-4 text-sm leading-6 text-tokyo-text';
  if (role === 'user') node.textContent = content; else node.innerHTML = marked.parse(content);
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
  const thinking = appendMessage('bot', '<span class="animate-pulse">Thinking...</span>', 'thinking');
  $('sendButton').disabled = true;
  try {
    const response = await fetch('/api/chat', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ repo_url: currentRepo, question, history: chatHistory }) });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || 'Chat request failed.');
    thinking.innerHTML = marked.parse(payload.answer);
    chatHistory.push({ role: 'user', content: question }, { role: 'model', content: payload.answer });
  } catch (error) { thinking.innerHTML = `<span class="text-red-300">${error.message}</span>`; } finally { $('sendButton').disabled = false; $('chatMessages').scrollTop = $('chatMessages').scrollHeight; }
}

$('questionInput').addEventListener('keydown', (event) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); sendQuestion(); } });