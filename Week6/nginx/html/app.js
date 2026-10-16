const endpoints = {
  node: '/api/node/health',
  python: '/api/python/health',
  rust: '/api/rust/health',
  db: '/api/node/health'
};

async function requestJson(url, options) {
  const response = await fetch(url, options);
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json();
}

async function refreshStatus() {
  await Promise.all(Object.entries(endpoints).map(async ([name, url]) => {
    const card = document.querySelector(`[data-service="${name}"]`);
    const pill = card.querySelector('.pill');
    try {
      const data = await requestJson(url);
      const healthy = name === 'db' ? data.database === 'connected' : data.status === 'ok';
      card.classList.toggle('up', healthy);
      card.classList.toggle('down', !healthy);
      pill.lastChild.textContent = healthy ? '正常' : '異常';
    } catch (_error) {
      card.classList.remove('up');
      card.classList.add('down');
      pill.lastChild.textContent = '離線';
    }
  }));
}

async function refreshMessages() {
  const list = document.querySelector('#messages');
  try {
    const messages = await requestJson('/api/node/messages');
    if (!messages.length) {
      list.innerHTML = '<p class="muted">還沒有留言，來寫下第一則吧。</p>';
      return;
    }
    list.innerHTML = messages.map((item) => `<article class="message"><div class="message-head"><strong>${escapeHtml(item.name)}</strong><time>${new Date(item.created_at).toLocaleString('zh-TW')}</time></div><p>${escapeHtml(item.message)}</p></article>`).join('');
  } catch (_error) {
    list.innerHTML = '<p class="muted">Node API 目前離線。</p>';
  }
}

async function refreshStats() {
  try {
    const stats = await requestJson('/api/python/stats');
    document.querySelector('#message-count').textContent = stats.message_count;
    document.querySelector('#average-length').textContent = stats.average_length;
    document.querySelector('#top-words').innerHTML = stats.top_words.length
      ? stats.top_words.map((item) => `<span class="word">${escapeHtml(item.word)}<b>${item.count}</b></span>`).join('')
      : '<span class="muted">還沒有足夠文字</span>';
  } catch (_error) {
    document.querySelector('#message-count').textContent = '—';
    document.querySelector('#average-length').textContent = '—';
    document.querySelector('#top-words').innerHTML = '<span class="muted">Python API 目前離線</span>';
  }
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[char]);
}

document.querySelector('#message-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const note = document.querySelector('#form-note');
  const values = Object.fromEntries(new FormData(form));
  note.textContent = '送出中…';
  try {
    await requestJson('/api/node/messages', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(values) });
    form.reset();
    note.textContent = '留言已寫入 PostgreSQL。';
    await Promise.all([refreshMessages(), refreshStats()]);
    refreshStatus();
  } catch (_error) {
    note.textContent = '送出失敗，請確認 Node 與資料庫服務狀態。';
  }
});

document.querySelector('#prime-button').addEventListener('click', async () => {
  const limit = Math.max(2, Math.min(10000, Number(document.querySelector('#prime-limit').value) || 100));
  const result = document.querySelector('#prime-result');
  result.textContent = 'Rust 計算中…';
  try {
    const data = await requestJson(`/api/rust/primes?limit=${limit}`);
    result.textContent = `小於等於 ${data.limit}：共 ${data.count} 個質數。${data.primes.join(', ')}`;
  } catch (_error) {
    result.textContent = 'Rust API 目前離線。';
  }
});

refreshStatus();
refreshMessages();
refreshStats();
setInterval(refreshStatus, 5000);
setInterval(() => { refreshMessages(); refreshStats(); }, 15000);
