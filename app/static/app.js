// ---------- DOM lookups ----------
const form = document.getElementById('searchForm');
const q = document.getElementById('q');
const sortSel = document.getElementById('sort');
const perpageSel = document.getElementById('perpage');
const mediaSel = document.getElementById('media');
const statusEl = document.getElementById('status');
const table = document.getElementById('results');
const tbody = table.querySelector('tbody');
const showHistoryBtn = document.getElementById('showHistoryBtn');

// Focus the search box
if (q) q.focus();

// Remember the media selector per browser (storage can be unavailable).
const MEDIA_KEY = 'bookfinder.media';
try {
  const saved = localStorage.getItem(MEDIA_KEY);
  if (mediaSel && saved && [...mediaSel.options].some(o => o.value === saved)) mediaSel.value = saved;
} catch {}
mediaSel?.addEventListener('change', () => {
  try { localStorage.setItem(MEDIA_KEY, mediaSel.value); } catch {}
});

const MEDIA_BADGE = { audiobook: '🎧', ebook: '📖' };
function mediaBadge(type) {
  const icon = MEDIA_BADGE[type];
  if (!icon) return '';
  return `<span class="badge" title="${type === 'ebook' ? 'Ebook' : 'Audiobook'}">${icon}</span>`;
}

// ---------- Health check ----------
(async () => {
  try {
    const r = await fetch('/health');
    const j = await r.json();
    document.getElementById('health').textContent = j.ok ? 'OK' : 'Not OK';
    const warn = document.getElementById('ingestWarn');
    if (warn && j.ebook_ingest && j.ebook_ingest !== 'ok' && j.ebook_ingest !== 'not configured') {
      warn.textContent = `Ebook import unavailable: ${j.ebook_ingest}`;
      warn.style.display = '';
    }
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
  const media = mediaSel?.value || 'audiobook';

  statusEl.textContent = 'Searching…';
  table.style.display = 'none';
  tbody.innerHTML = '';

  try {
    const resp = await fetch('/search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ tor: { text, sortType }, perpage, media })
    });
    if (!resp.ok) {
      let msg = `HTTP ${resp.status}`;
      try {
        const j = await resp.json();
        if (j?.detail) msg = j.detail;
      } catch {}
      throw new Error(msg);
    }
    const data = await resp.json();

    const rows = data.results || [];
    if (!rows.length) {
      statusEl.textContent = 'No results.';
      return;
    }

    // Torrents of the same book share it.group (same media type, authors and
    // series number or title); show one row per book with its other versions
    // behind a toggle. Groups keep MAM's sort order.
    const groups = new Map();
    rows.forEach((it) => {
      const key = it.group || `id:${it.id}`;
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key).push(it);
    });

    groups.forEach((items) => {
      const [first, ...others] = items;
      const tr = makeResultRow(first);
      tbody.appendChild(tr);
      if (!others.length) return;

      const versionRows = others.map((it) => {
        const vr = makeResultRow(it);
        vr.className = 'version';
        vr.style.display = 'none';
        tbody.appendChild(vr);
        return vr;
      });
      const formats = [...new Set(items.map(it => it.format).filter(Boolean))].join(' · ');
      const toggle = document.createElement('button');
      toggle.type = 'button';
      toggle.className = 'versions-toggle';
      const label = (open) => `${open ? '▾' : '▸'} ${items.length} versions${formats ? ` (${formats})` : ''}`;
      toggle.textContent = label(false);
      toggle.addEventListener('click', () => {
        const open = versionRows[0].style.display === 'none';
        versionRows.forEach(vr => { vr.style.display = open ? '' : 'none'; });
        toggle.textContent = label(open);
      });
      tr.firstElementChild.appendChild(document.createElement('br'));
      tr.firstElementChild.appendChild(toggle);
    });

    table.style.display = '';
    statusEl.textContent = groups.size === rows.length
      ? `${rows.length} results shown`
      : `${rows.length} results shown (${groups.size} books)`;
    await loadHistory();
  } catch (e) {
    console.error(e);
    statusEl.textContent = `Search failed: ${e.message}`;
  }
}

// ---------- Result rows ----------
function makeResultRow(it) {
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
          narrator: it.narrator_info || '',
          media_type: it.media_type || 'audiobook'
        })
      });
      if (resp.status === 409) {
        addBtn.textContent = 'Already in qB';
        addBtn.title = 'This torrent is already in qBittorrent';
        return;
      }
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
      addBtn.title = e.message;
      addBtn.disabled = false;
      statusEl.textContent = `Add failed: ${e.message}`;
    }
  });

  // Torrent details link on MAM
  const detailsURL = it.id ? `https://www.myanonamouse.net/t/${encodeURIComponent(it.id)}` : '';

  tr.innerHTML = `
    <td>${mediaBadge(it.media_type)}${escapeHtml(it.title || '')}${it.series ? `<div class="muted">${escapeHtml(it.series)}</div>` : ''}</td>
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
  return tr;
}

// ---------- Ebook import (Grimmory) ----------
// One torrent can hold several formats of a book; the user ticks what to copy
// (preferred format pre-ticked). Files are always copied, never linked.
async function openEbookImport(expTd, h, tr, close) {
  expTd.innerHTML = `
    <div class="import-form" style="padding:8px;border:1px solid #ddd;border-radius:8px;margin:6px 0;">
      <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center;">
        <span>Import to Grimmory from:</span>
        <select class="imp-torrent" style="min-width:280px;max-width:100%;">
          <option disabled selected>Loading torrents…</option>
        </select>
      </div>
      <div class="imp-files" style="margin-top:8px;"></div>
      <button class="imp-go" style="margin-top:8px;" disabled>Copy to Grimmory</button>
      <div class="imp-status" style="margin-top:6px;color:#666;"></div>
    </div>
  `;
  const sel   = expTd.querySelector('.imp-torrent');
  const box   = expTd.querySelector('.imp-files');
  const goBtn = expTd.querySelector('.imp-go');
  const st    = expTd.querySelector('.imp-status');

  const errorOf = async (r) => {
    let msg = `HTTP ${r.status}`;
    try { const j = await r.json(); if (j?.detail) msg += ` — ${j.detail}`; } catch {}
    return msg;
  };

  const loadChoices = async () => {
    box.textContent = 'Loading files…';
    goBtn.disabled = true;
    try {
      const r = await fetch(`/import/ebook-choices?hash=${encodeURIComponent(sel.value)}`);
      if (!r.ok) throw new Error(await errorOf(r));
      const books = (await r.json()).books || [];
      box.innerHTML = '';
      if (!books.length) { box.textContent = 'No ebook files in this torrent.'; return; }
      books.forEach((b) => {
        const div = document.createElement('div');
        div.style.margin = '4px 0';
        const name = document.createElement('div');
        name.textContent = b.book;
        name.style.fontWeight = '600';
        div.appendChild(name);
        b.files.forEach((f) => {
          const label = document.createElement('label');
          label.style.display = 'block';
          label.style.marginLeft = '1rem';
          const cb = document.createElement('input');
          cb.type = 'checkbox';
          cb.value = f.path;
          cb.checked = !!f.selected;
          cb.addEventListener('change', () => { goBtn.disabled = !box.querySelector('input:checked'); });
          label.appendChild(cb);
          label.append(` ${f.format.toUpperCase()} · ${formatSize(f.size)}`);
          label.title = f.path;
          div.appendChild(label);
        });
        box.appendChild(div);
      });
      goBtn.disabled = !box.querySelector('input:checked');
    } catch (e) {
      console.error(e);
      box.textContent = `Failed to list files: ${e.message}`;
    }
  };

  try {
    const r = await fetch('/qb/torrents?media=ebook');
    if (!r.ok) throw new Error(await errorOf(r));
    const items = (await r.json()).items || [];
    sel.innerHTML = '';
    items.forEach((t) => {
      const opt = document.createElement('option');
      opt.value = t.hash;
      opt.textContent = t.name;
      if (h.qb_hash && t.hash === h.qb_hash) opt.selected = true;
      sel.appendChild(opt);
    });
    if (!items.length) {
      sel.innerHTML = '<option disabled selected>No completed ebook torrents</option>';
      return;
    }
    sel.addEventListener('change', loadChoices);
    await loadChoices();
  } catch (e) {
    console.error(e);
    sel.innerHTML = '<option disabled selected>Failed to load torrents</option>';
    st.textContent = e.message;
    return;
  }

  goBtn.addEventListener('click', async (ev) => {
    ev.preventDefault();
    const files = [...box.querySelectorAll('input:checked')].map(cb => cb.value);
    if (!files.length) return;
    goBtn.disabled = true;
    st.textContent = 'Copying…';
    try {
      const r = await fetch('/import', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ hash: sel.value, history_id: h.id, files })
      });
      if (!r.ok) throw new Error(await errorOf(r));
      const jr = await r.json();
      statusEl.textContent = `${h.title || 'Ebook'}: copied to Grimmory (${(jr.files || []).join(', ')})`;
      const statusTd = tr.children[5];
      if (statusTd) statusTd.textContent = 'imported';
      close();  // success: hide the panel; the result is in the status line
    } catch (e) {
      console.error(e);
      st.textContent = `Failed: ${e.message}`;
      goBtn.disabled = false;
    }
  });
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
      const isEbook = h.media_type === 'ebook';
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
        <td>${mediaBadge(h.media_type || 'audiobook')}${escapeHtml(h.title || '')}</td>
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

const closeImport = () => {
  exp.style.display = 'none';
  expTd.innerHTML = '';
};

importBtn.addEventListener('click', async () => {
  // toggle open/close
  if (exp.style.display === '') {
    closeImport();
    return;
  }
  exp.style.display = '';
  if (isEbook) {
    await openEbookImport(expTd, h, tr, closeImport);
    return;
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
        <button class="imp-go">Copy to Library</button>
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
    const r = await fetch(`/qb/torrents?media=${encodeURIComponent(h.media_type || 'audiobook')}`);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const j = await r.json();
    sel.innerHTML = '';
    (j.items || []).forEach(t => {
      const opt = document.createElement('option');
      opt.value = t.hash;
      opt.textContent = `${t.name}  —  ${t.single_file ? 'single-file' : (t.root || t.name)}`;
      if (h.qb_hash && t.hash === h.qb_hash) opt.selected = true;
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
      statusEl.textContent = `${title}: imported → ${jr.dest}`;
      
      // update Status cell in this row: columns are
      // 0 Title, 1 Author, 2 Narrator, 3 Link, 4 When, 5 Status, 6 Import, 7 Remove
      const statusTd = tr.children[5];
      if (statusTd) statusTd.textContent = 'imported';
      closeImport();  // success: hide the panel; the result is in the status line

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