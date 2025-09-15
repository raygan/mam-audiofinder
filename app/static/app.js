// ---------- DOM lookups ----------
const form = document.getElementById('searchForm');   // <form id="searchForm"> … </form>
const q = document.getElementById('q');
const sortSel = document.getElementById('sort');
const perpageSel = document.getElementById('perpage');
const statusEl = document.getElementById('status');
const table = document.getElementById('results');
const tbody = table.querySelector('tbody');
const showHistoryBtn = document.getElementById('showHistoryBtn');

// Focus the search box (if present)
if (q) q.focus();

// ---------- Health check ----------
(async () => {
  try {
    const r = await fetch('/health');
    const j = await r.json();
    document.getElementById('health').textContent = j.ok ? 'OK' : 'Not OK';
  } catch {
    document.getElementById('health').textContent = 'Error';
  }
})();

// Show history even without searching
if (showHistoryBtn) {
  showHistoryBtn.addEventListener('click', async () => {
    const card = document.getElementById('historyCard');
    card.style.display = '';
    await loadHistory();
    card.scrollIntoView({ behavior: 'smooth', block: 'start' });
  });
}

// ---------- Submit handler (Enter or button) ----------
form.addEventListener('submit', async (e) => {
  e.preventDefault();
  await runSearch();
});

// ---------- Search flow ----------
async function runSearch() {
  const text = q.value.trim();
  const sortType = sortSel.value;
  const perpage = parseInt(perpageSel.value, 10);

  statusEl.textContent = 'Searching…';
  table.style.display = 'none';
  tbody.innerHTML = '';

  try {
    const resp = await fetch('/search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ tor: { text, sortType }, perpage })
    });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();

    const rows = data.results || [];
    if (!rows.length) {
      statusEl.textContent = 'No results.';
      return;
    }

    rows.forEach((it) => {
      const tr = document.createElement('tr');
      const sl = `${it.seeders ?? '-'} / ${it.leechers ?? '-'}`;

      // Add-to-qB button
      const addBtn = document.createElement('button');
      addBtn.textContent = 'Add';
      // enable if we have a direct dl hash OR at least an id (backend will fall back to cookie fetch)
      addBtn.disabled = !(it.dl || it.id);
      addBtn.addEventListener('click', async () => {
        addBtn.disabled = true;
        addBtn.textContent = 'Adding…';
        try {
          const resp = await fetch('/add', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              id: String(it.id ?? ''),
              title: it.title || '',
              dl: it.dl || ''
            })
          });
          if (!resp.ok) {
            let msg = `HTTP ${resp.status}`;
            try {
              const j = await resp.json();
              if (j?.detail) msg += ` — ${j.detail}`;
            } catch {}
            throw new Error(msg);
          }
          addBtn.textContent = 'Added';
          await loadHistory();
        } catch (e) {
          console.error(e);
          addBtn.textContent = 'Error';
          addBtn.disabled = false;
        }
      });

      // Torrent details link on MAM
      const detailsURL = it.id ? `https://www.myanonamouse.net/t/${encodeURIComponent(it.id)}` : '';

      tr.innerHTML = `
        <td>${escapeHtml(it.title || '')}</td>
        <td>${escapeHtml(it.author_info || '')}</td>
        <td>${escapeHtml(it.narrator_info || '')}</td>
        <td>${escapeHtml(it.format || '')}</td>
        <td class="right">${formatSize(it.size)}</td>
        <td class="right">${sl}</td>
        <td>${escapeHtml(it.added || '')}</td>
        <td class="center">
          ${detailsURL ? `<a href="${detailsURL}" target="_blank" rel="noopener noreferrer" title="Open on MAM">🔗</a>` : ''}
        </td>
        <td></td>
      `;
      tr.lastElementChild.appendChild(addBtn);
      tbody.appendChild(tr);
    });

    table.style.display = '';
    statusEl.textContent = `${rows.length} results shown`;
    await loadHistory();
  } catch (e) {
    console.error(e);
    statusEl.textContent = 'Search failed.';
  }
}

// ---------- Helpers ----------
function escapeHtml(s) {
  return (s || '').toString()
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;');
}

function formatSize(sz) {
  if (!sz) return '';
  const n = Number(sz);
  if (!Number.isFinite(n)) return String(sz);
  const units = ['B','KB','MB','GB','TB'];
  let i = 0, x = n;
  while (x >= 1024 && i < units.length - 1) { x /= 1024; i++; }
  return `${x.toFixed(1)} ${units[i]}`;
}

async function loadHistory() {
  try {
    const r = await fetch('/history');
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const j = await r.json();
    const card = document.getElementById('historyCard');
    const hist = document.getElementById('history');
    const tbody = hist.querySelector('tbody');
    tbody.innerHTML = '';

    (j.items || []).forEach((h) => {
      const tr = document.createElement('tr');
      const when = h.added_at ? new Date(h.added_at.replace(' ', 'T') + 'Z').toLocaleString() : '';

      const rmBtn = document.createElement('button');
      rmBtn.textContent = 'Remove';
      rmBtn.addEventListener('click', async () => {
        rmBtn.disabled = true;
        try {
          const resp = await fetch(`/history/${encodeURIComponent(h.id)}`, { method: 'DELETE' });
          if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
          tr.remove();
          const hasRows = tbody.children.length > 0;
          card.style.display = hasRows ? '' : 'none';
        } catch (e) {
          console.error('remove failed', e);
          rmBtn.disabled = false;
        }
      });

      tr.innerHTML = `
        <td>${escapeHtml(h.title || '')}</td>
        <td>${escapeHtml(when)}</td>
        <td>${escapeHtml(h.qb_status || '')}</td>
        <td></td>
      `;
      tr.lastElementChild.appendChild(rmBtn);
      tbody.appendChild(tr);
    });

    card.style.display = (j.items && j.items.length) ? '' : 'none';
  } catch (e) {
    console.error('history load failed', e);
  }
}