// ---------- DOM lookups ----------
const form = document.getElementById('searchForm');
const q = document.getElementById('q');
const sortSel = document.getElementById('sort');
const perpageSel = document.getElementById('perpage');
const statusEl = document.getElementById('status');
const table = document.getElementById('results');
const tbody = table.querySelector('tbody');
const showHistoryBtn = document.getElementById('showHistoryBtn');

// Focus the search box
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

// ---------- Show History (even without searching) ----------
if (showHistoryBtn) {
  showHistoryBtn.addEventListener('click', async () => {
    const card = document.getElementById('historyCard');
    card.style.display = '';           // reveal card
    await loadHistory();               // populate
    card.scrollIntoView({ behavior: 'smooth', block: 'start' });
  });
}

// ---------- Submit handler (Enter or button) ----------
if (form) {
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    await runSearch();
  });
}

// ---------- Search flow ----------
async function runSearch() {
  const text = (q?.value || '').trim();
  const sortType = (sortSel?.value) || 'default';
  const perpage = parseInt(perpageSel?.value || '25', 10);

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
      // enable if we have a direct dl hash OR at least an id
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
              dl: it.dl || '',
              author: it.author_info || '',
              narrator: it.narrator_info || ''
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
  if (sz == null || sz === '') return '';
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
    const htbody = hist.querySelector('tbody');
    htbody.innerHTML = '';

    const items = j.items || [];

    if (!items.length) {
      // show empty state row instead of hiding the card
      const colSpan = hist.querySelector('thead tr').children.length;
      const tr = document.createElement('tr');
      tr.className = 'empty';
      tr.innerHTML = `<td colspan="${colSpan}" class="center muted">No items in history yet.</td>`;
      htbody.appendChild(tr);
      card.style.display = ''; // keep the card visible
      return;
    }

    items.forEach((h) => {
      const tr = document.createElement('tr');
      const when = h.added_at ? new Date(h.added_at.replace(' ', 'T') + 'Z').toLocaleString() : '';
      const linkURL = h.mam_id ? `https://www.myanonamouse.net/t/${encodeURIComponent(h.mam_id)}` : '';

      // buttons
      const importBtn = document.createElement('button');
      importBtn.textContent = 'Import';
      const rmBtn = document.createElement('button');
      rmBtn.textContent = 'Remove';
      rmBtn.addEventListener('click', async () => {
        rmBtn.disabled = true;
        try {
          const resp = await fetch(`/history/${encodeURIComponent(h.id)}`, { method: 'DELETE' });
          if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
          tr.remove();
          // if we just removed the last row, render the empty state
          if (!htbody.children.length) {
            const colSpan = hist.querySelector('thead tr').children.length;
            const emptyTr = document.createElement('tr');
            emptyTr.className = 'empty';
            emptyTr.innerHTML = `<td colspan="${colSpan}" class="center muted">No items in history yet.</td>`;
            htbody.appendChild(emptyTr);
          }
        } catch (e) {
          console.error('remove failed', e);
          rmBtn.disabled = false;
        }
      });

      tr.innerHTML = `
        <td>${escapeHtml(h.title || '')}</td>
        <td>${escapeHtml(h.author || '')}</td>
        <td>${escapeHtml(h.narrator || '')}</td>
        <td class="center">${linkURL ? `<a href="${linkURL}" target="_blank" rel="noopener noreferrer" title="Open on MAM">🔗</a>` : ''}</td>
        <td>${escapeHtml(when)}</td>
        <td>${escapeHtml(h.qb_status || '')}</td>
        <td></td>   <!-- Import -->
        <td></td>   <!-- Remove -->
      `;
      tr.children[tr.children.length - 2].appendChild(importBtn);
      tr.lastElementChild.appendChild(rmBtn);
      htbody.appendChild(tr);

// expander row (initially hidden)
const exp = document.createElement('tr');
exp.style.display = 'none';
const expTd = document.createElement('td');
expTd.colSpan = hist.querySelector('thead tr').children.length; // match column count
exp.appendChild(expTd);
htbody.appendChild(exp);

importBtn.addEventListener('click', async () => {
  // toggle open/close
  if (exp.style.display === '') {
    exp.style.display = 'none';
    expTd.innerHTML = '';
    return;
  }
  exp.style.display = '';

  // Fetch config to get import mode
  let buttonText = 'Copy to Library';
  try {
    const cfgResp = await fetch('/config');
    if (cfgResp.ok) {
      const cfg = await cfgResp.json();
      if (cfg.import_mode === 'link') {
        buttonText = 'Link to Library';
      } else if (cfg.import_mode === 'move') {
        buttonText = 'Move to Library';
      }
    }
  } catch (e) {
    console.error('Failed to fetch config', e);
  }

  expTd.innerHTML = `
    <div class="import-form" style="padding:8px;border:1px solid #ddd;border-radius:8px;margin:6px 0;">
      <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center;">
        <span>Import:</span>
        <span>/</span>
        <input type="text" class="imp-author" placeholder="Author" value="${escapeHtml(h.author || '')}" style="min-width:220px;">
        <span>/</span>
        <input type="text" class="imp-title" placeholder="Title" value="${escapeHtml(h.title || '')}" style="min-width:280px;">
        <span>/</span>
        <select class="imp-torrent" style="min-width:320px;">
          <option disabled selected>Loading torrents…</option>
        </select>
        <button class="imp-go">${buttonText}</button>
      </div>
      <div class="imp-status" style="margin-top:6px;color:#666;"></div>
    </div>
  `;

  const authorInput = expTd.querySelector('.imp-author');
  const titleInput  = expTd.querySelector('.imp-title');
  const sel         = expTd.querySelector('.imp-torrent');
  const goBtn       = expTd.querySelector('.imp-go');
  const st          = expTd.querySelector('.imp-status');

  // load torrents in our qB category
  try {
    const r = await fetch('/qb/torrents');
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const j = await r.json();
    sel.innerHTML = '';
    (j.items || []).forEach(t => {
      const opt = document.createElement('option');
      opt.value = t.hash;
      opt.textContent = `${t.name}  —  ${t.single_file ? 'single-file' : (t.root || t.name)}`;
      sel.appendChild(opt);
    });
    if (!sel.children.length) {
      const opt = document.createElement('option');
      opt.disabled = true; opt.selected = true;
      opt.textContent = 'No completed torrents in category';
      sel.appendChild(opt);
    }
  } catch (e) {
    console.error(e);
    sel.innerHTML = '<option disabled selected>Failed to load torrents</option>';
  }

  goBtn.addEventListener('click', async (ev) => {
    ev.preventDefault();
    const author = authorInput.value.trim();
    const title  = titleInput.value.trim();
    const hash   = sel.value;
    if (!author || !title || !hash) {
      st.textContent = 'Please fill Author, Title, and select a torrent.';
      return;
    }
    goBtn.disabled = true;
    st.textContent = 'Importing…';
    try {
      console.log('import payload', { author, title, hash, history_id: h.id });  // logging to troubleshoot mark-as-imported
      const r = await fetch('/import', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          author,
          title,
          hash,
          history_id: h.id
        })
      });
      if (!r.ok) {
        let msg = `HTTP ${r.status}`;
        try { const j = await r.json(); if (j?.detail) msg += ` — ${j.detail}`; } catch {}
        throw new Error(msg);
      }
      const jr = await r.json();

      // Build status message with statistics
      let statusMsg = `Done → ${jr.dest} (${jr.files_copied || '?'} files`;
      if (jr.import_mode === 'link') {
        if (jr.files_linked > 0) {
          statusMsg += `, ${jr.files_linked} hardlinked`;
          if (jr.files_copied > jr.files_linked) {
            statusMsg += `, ${jr.files_copied - jr.files_linked} copied`;
          }
        } else {
          statusMsg += ', all copied (hardlink failed)';
        }
      } else if (jr.import_mode === 'move') {
        statusMsg += ', moved';
      } else {
        statusMsg += ', copied';
      }
      statusMsg += ')';

      st.textContent = statusMsg;
      goBtn.textContent = jr.import_mode === 'link' ? 'Linked' : jr.import_mode === 'move' ? 'Moved' : 'Imported';
      
      // update Status cell in this row: columns are
      // 0 Title, 1 Author, 2 Narrator, 3 Link, 4 When, 5 Status, 6 Import, 7 Remove
      const statusTd = tr.children[5];
      if (statusTd) statusTd.textContent = 'imported';

      // Bonus: refresh the torrents list so this one disappears if you clear/move category server-side
      // (optional) const _ = await fetch('/qb/torrents'); // ignore result
    } catch (e) {
      console.error(e);
      st.textContent = `Failed: ${e.message}`;
      goBtn.disabled = false;
    }
  });
});
    });

    card.style.display = ''; // always visible
  } catch (e) {
    console.error('history load failed', e);
  }
}