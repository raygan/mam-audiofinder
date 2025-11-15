// ---------- DOM lookups ----------
const form = document.getElementById('searchForm');
const q = document.getElementById('q');
const sortSel = document.getElementById('sort');
const perpageSel = document.getElementById('perpage');
const statusEl = document.getElementById('status');
const table = document.getElementById('results');
const tbody = table.querySelector('tbody');
const showHistoryBtn = document.getElementById('showHistoryBtn');

// ---------- URL State Management ----------
function getStateFromURL() {
  const params = new URLSearchParams(window.location.search);
  return {
    q: params.get('q') || '',
    sort: params.get('sort') || 'default',
    perpage: params.get('perpage') || '25',
    view: params.get('view') || ''
  };
}

function updateURL(state, replace = false) {
  const params = new URLSearchParams();

  if (state.q) params.set('q', state.q);
  if (state.sort && state.sort !== 'default') params.set('sort', state.sort);
  if (state.perpage && state.perpage !== '25') params.set('perpage', state.perpage);
  if (state.view) params.set('view', state.view);

  const newURL = params.toString()
    ? `${window.location.pathname}?${params.toString()}`
    : window.location.pathname;

  if (replace) {
    window.history.replaceState(state, '', newURL);
  } else {
    window.history.pushState(state, '', newURL);
  }
}

function getCurrentState() {
  // Determine current view based on visible cards
  let currentView = '';
  if (document.getElementById('historyCard')?.style.display === '') {
    currentView = 'history';
  } else if (document.getElementById('logsCard')?.style.display === '') {
    currentView = 'logs';
  }

  return {
    q: (q?.value || '').trim(),
    sort: (sortSel?.value) || 'default',
    perpage: (perpageSel?.value) || '25',
    view: currentView
  };
}

// Focus the search box (unless we're restoring state from URL)
const urlState = getStateFromURL();
if (!urlState.q) {
  if (q) q.focus();
}

// ---------- Health check ----------
(async () => {
  try {
    const r = await fetch('/health');
    const j = await r.json();
    const healthText = j.ok ? 'OK' : 'Not OK';
    document.getElementById('health').textContent = healthText;

    // Update task bar health indicator
    const healthIndicator = document.getElementById('navHealth');
    const healthDot = healthIndicator?.querySelector('.health-dot');
    const healthTextEl = healthIndicator?.querySelector('.health-text');
    if (healthIndicator && healthDot && healthTextEl) {
      healthTextEl.textContent = healthText;
      if (j.ok) {
        healthIndicator.classList.add('ok');
        healthIndicator.classList.remove('error');
      } else {
        healthIndicator.classList.add('error');
        healthIndicator.classList.remove('ok');
      }
    }
  } catch {
    document.getElementById('health').textContent = 'Error';
    const healthIndicator = document.getElementById('navHealth');
    const healthTextEl = healthIndicator?.querySelector('.health-text');
    if (healthIndicator && healthTextEl) {
      healthTextEl.textContent = 'Error';
      healthIndicator.classList.add('error');
      healthIndicator.classList.remove('ok');
    }
  }
})();

// ---------- View Management ----------
const views = {
  search: { card: null, navBtn: 'navSearch' },  // Search has no card, uses results table
  history: { card: 'historyCard', navBtn: 'navHistory' },
  logs: { card: 'logsCard', navBtn: 'navLogs' }
};

function showView(viewName) {
  // Update active nav button
  Object.values(views).forEach(view => {
    const btn = document.getElementById(view.navBtn);
    if (btn) btn.classList.remove('active');
  });

  const activeBtn = document.getElementById(views[viewName]?.navBtn);
  if (activeBtn) activeBtn.classList.add('active');

  // Show/hide cards
  Object.entries(views).forEach(([name, view]) => {
    if (view.card) {
      const card = document.getElementById(view.card);
      if (card) {
        card.style.display = (name === viewName) ? '' : 'none';
      }
    }
  });

  // Handle search view special case
  if (viewName === 'search') {
    // Don't hide results table, user might want to keep search results visible
    // Just make sure the search form is visible
  }

  // Scroll to appropriate section
  if (viewName !== 'search') {
    const card = document.getElementById(views[viewName]?.card);
    if (card) {
      card.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  } else {
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }
}

// ---------- Task Bar Navigation ----------
document.getElementById('navSearch')?.addEventListener('click', () => {
  showView('search');
  updateURL({ ...getCurrentState(), view: '' }, true);
  if (q) q.focus();
});

document.getElementById('navHistory')?.addEventListener('click', async () => {
  showView('history');
  await loadHistory();
  updateURL({ ...getCurrentState(), view: 'history' }, true);
});

document.getElementById('navLogs')?.addEventListener('click', async () => {
  showView('logs');
  await loadLogs();
  updateURL({ ...getCurrentState(), view: 'logs' }, true);
});

// ---------- Logs View ----------
async function loadLogs() {
  const logsContent = document.getElementById('logsContent');
  const logLevel = document.getElementById('logLevel')?.value || '';
  const logLines = parseInt(document.getElementById('logLines')?.value || '100', 10);
  const autoScroll = document.getElementById('autoScrollLogs')?.checked;

  if (!logsContent) return;

  try {
    logsContent.textContent = 'Loading logs...';

    const params = new URLSearchParams({
      lines: logLines.toString(),
      level: logLevel
    });

    const resp = await fetch(`/api/logs?${params}`);
    if (!resp.ok) {
      logsContent.textContent = `Error loading logs: HTTP ${resp.status}`;
      return;
    }

    const data = await resp.json();

    if (!data.ok) {
      logsContent.textContent = `Error: ${data.error || 'Unknown error'}`;
      return;
    }

    if (!data.logs || data.logs.length === 0) {
      logsContent.textContent = 'No logs found.';
      return;
    }

    // Display logs with basic syntax highlighting
    const logsText = data.logs.join('');
    logsContent.innerHTML = highlightLogs(logsText);

    // Auto-scroll to bottom if enabled
    if (autoScroll) {
      const container = document.getElementById('logsContainer');
      if (container) {
        container.scrollTop = container.scrollHeight;
      }
    }

  } catch (error) {
    console.error('Error loading logs:', error);
    logsContent.textContent = `Error loading logs: ${error.message}`;
  }
}

function highlightLogs(text) {
  // Basic syntax highlighting for log levels
  return escapeHtml(text)
    .replace(/\b(INFO)\b/g, '<span class="log-info">$1</span>')
    .replace(/\b(WARNING)\b/g, '<span class="log-warning">$1</span>')
    .replace(/\b(ERROR)\b/g, '<span class="log-error">$1</span>');
}

// Logs controls
document.getElementById('refreshLogsBtn')?.addEventListener('click', async () => {
  await loadLogs();
});

document.getElementById('logLevel')?.addEventListener('change', async () => {
  await loadLogs();
});

document.getElementById('logLines')?.addEventListener('change', async () => {
  await loadLogs();
});

// ---------- Show History (even without searching) ----------
if (showHistoryBtn) {
  showHistoryBtn.addEventListener('click', async () => {
    const card = document.getElementById('historyCard');
    card.style.display = '';           // reveal card
    await loadHistory();               // populate
    card.scrollIntoView({ behavior: 'smooth', block: 'start' });

    // Update URL to reflect history view
    updateURL(getCurrentState(), true);
  });
}

// ---------- Submit handler (Enter or button) ----------
if (form) {
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    await runSearch();
  });
}

// ---------- Cover lazy loading with IntersectionObserver ----------
const rowStateStore = new Map();
let coverObserver = null;

function initCoverObserver() {
  if (coverObserver) return coverObserver;

  coverObserver = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        const container = entry.target;
        const mamId = container.dataset.mamId;
        const title = container.dataset.title;
        const author = container.dataset.author;
        const rowId = container.dataset.rowId;
        const rowState = rowId ? rowStateStore.get(rowId) : null;

        // Stop observing immediately to avoid duplicate fetches
        coverObserver.unobserve(container);

        if (!mamId || !title) {
          container.innerHTML = '<div class="cover-placeholder">No info</div>';
          return;
        }

        // Fetch cover from backend with retry logic
        fetchCoverForItem(container, mamId, title, author, rowState);
      }
    });
  }, {
    rootMargin: '50px', // Start loading 50px before entering viewport
    threshold: 0.01
  });

  return coverObserver;
}

async function fetchCoverForItem(container, mamId, title, author, rowState = null) {
  try {
    container.classList.remove('cover-loaded');
    const params = new URLSearchParams({
      mam_id: mamId,
      title: title,
      author: author || '',
      max_retries: '2'
    });

    const resp = await fetch(`/api/covers/fetch?${params}`);
    if (!resp.ok) {
      console.error(`Cover fetch failed: HTTP ${resp.status}`);
      container.innerHTML = '<div class="cover-placeholder">Error</div>';
      return;
    }

    const data = await resp.json();

    if (data.cover_url) {
      if (rowState) {
        rowState.abs_cover_url = data.cover_url;
        rowState.abs_item_id = data.item_id || rowState.abs_item_id || '';
      }
      // Create and load the image
      const img = document.createElement('img');
      img.className = 'cover-image';
      img.alt = 'Cover';
      img.src = data.cover_url;

      img.onload = () => {
        img.classList.add('loaded');
        container.innerHTML = '';
        container.appendChild(img);
        container.classList.add('cover-loaded');
      };

      img.onerror = () => {
        container.innerHTML = '<div class="cover-placeholder">No cover</div>';
        container.classList.remove('cover-loaded');
      };
    } else {
      if (rowState) {
        rowState.abs_cover_url = '';
        rowState.abs_item_id = '';
      }
      // No cover available or error
      const errorMsg = data.error || 'No cover';
      container.innerHTML = `<div class="cover-placeholder">${errorMsg === 'No cover found' ? 'No cover' : 'Error'}</div>`;
      container.classList.remove('cover-loaded');
    }
  } catch (e) {
    console.error('Cover fetch exception:', e);
    container.innerHTML = '<div class="cover-placeholder">Error</div>';
    container.classList.remove('cover-loaded');
  }
}

// ---------- Search flow ----------
async function runSearch() {
  rowStateStore.clear();
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

    // Initialize the cover observer
    const observer = initCoverObserver();

    // Render rows immediately with skeleton placeholders
    rows.forEach((it, idx) => {
      const rowId = `${it.id || 'row'}-${idx}`;
      const rowState = {
        ...it,
        abs_cover_url: it.abs_cover_url || '',
        abs_item_id: it.abs_item_id || ''
      };
      rowStateStore.set(rowId, rowState);

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
              id: String(rowState.id ?? ''),
              title: rowState.title || '',
              dl: rowState.dl || '',
              author: rowState.author_info || '',
              narrator: rowState.narrator_info || '',
              abs_cover_url: rowState.abs_cover_url || '',
              abs_item_id: rowState.abs_item_id || ''
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

      // Create cover container with skeleton placeholder
      const coverContainer = document.createElement('div');
      coverContainer.className = 'cover-skeleton';
      coverContainer.dataset.mamId = it.id || '';
      coverContainer.dataset.title = it.title || '';
      coverContainer.dataset.author = it.author_info || '';
      coverContainer.dataset.rowId = rowId;

      // Create the row structure
      const coverCell = document.createElement('td');
      coverCell.style.padding = '0.25rem';
      coverCell.appendChild(coverContainer);

      tr.innerHTML = `
        <td style="padding: 0.25rem;"></td>
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

      // Replace the first cell with our cover cell
      tr.replaceChild(coverCell, tr.firstElementChild);

      // Add the Add button
      tr.lastElementChild.appendChild(addBtn);
      tbody.appendChild(tr);

      // Observe the cover container for lazy loading
      observer.observe(coverContainer);
    });

    // Show table immediately with skeleton placeholders
    table.style.display = '';
    statusEl.textContent = `${rows.length} results shown`;

    // Update URL with search parameters
    updateURL(getCurrentState(), true);

    // Load history in parallel (non-blocking)
    loadHistory().catch(e => console.error('Failed to load history:', e));
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

      // Cover image (if available)
      const coverHTML = h.abs_cover_url
        ? `<img src="${escapeHtml(h.abs_cover_url)}" alt="Cover" style="max-width: 60px; max-height: 90px; width: auto; height: auto; display: block;" loading="lazy" onerror="this.style.display='none'">`
        : '<span style="color: #666; font-size: 0.8em;">No cover</span>';

      // Color-coded status display
      const statusColor = h.qb_status_color || 'grey';
      const colorMap = {
        'grey': '#999',
        'blue': '#3498db',
        'yellow': '#f39c12',
        'green': '#27ae60',
        'red': '#e74c3c'
      };
      const statusStyle = `color: ${colorMap[statusColor] || '#999'}; font-weight: 500;`;

      // Path warning indicator
      const pathWarningIcon = h.path_warning
        ? `<span style="color: #e74c3c; cursor: help; margin-left: 4px;" title="${escapeHtml(h.path_warning)}">⚠️</span>`
        : '';

      tr.innerHTML = `
        <td style="padding: 0.25rem;">${coverHTML}</td>
        <td>${escapeHtml(h.title || '')}</td>
        <td>${escapeHtml(h.author || '')}</td>
        <td>${escapeHtml(h.narrator || '')}</td>
        <td class="center">${linkURL ? `<a href="${linkURL}" target="_blank" rel="noopener noreferrer" title="Open on MAM">🔗</a>` : ''}</td>
        <td>${escapeHtml(when)}</td>
        <td><span style="${statusStyle}">${escapeHtml(h.qb_status || '')}</span>${pathWarningIcon}</td>
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
    <div class="import-form">
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
      <div style="display:flex;gap:12px;margin-top:8px;align-items:center;flex-wrap:wrap;">
        <label style="display:flex;align-items:center;gap:4px;cursor:pointer;">
          <input type="checkbox" class="imp-flatten" style="cursor:pointer;">
          <span>Flatten multi-disc structure</span>
        </label>
        <button class="imp-view-files" style="font-size:0.9em;">📁 View Files</button>
        <span class="imp-detection-hint" style="font-size:0.9em;color:#666;"></span>
      </div>
      <div class="imp-tree-view" style="display:none;"></div>
      <div class="imp-status" style="margin-top:6px;color:#666;"></div>
    </div>
  `;

  const authorInput = expTd.querySelector('.imp-author');
  const titleInput  = expTd.querySelector('.imp-title');
  const sel         = expTd.querySelector('.imp-torrent');
  const goBtn       = expTd.querySelector('.imp-go');
  const st          = expTd.querySelector('.imp-status');
  const flattenCheckbox = expTd.querySelector('.imp-flatten');
  const viewFilesBtn = expTd.querySelector('.imp-view-files');
  const treeView = expTd.querySelector('.imp-tree-view');
  const detectionHint = expTd.querySelector('.imp-detection-hint');

  // Store tree data for the selected torrent
  let treeData = null;

  // load torrents in our qB category
  let torrents = [];
  let matchedTorrent = null;
  try {
    const r = await fetch('/qb/torrents');
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const j = await r.json();
    torrents = j.items || [];
    sel.innerHTML = '';

    // Find matching torrent using priority: hash > mam_id > title
    const historyHash = h.qb_hash;
    const historyMamId = String(h.mam_id || '').trim();

    if (torrents.length) {
      // Try to match by hash first
      if (historyHash) {
        matchedTorrent = torrents.find(t => t.hash === historyHash);
      }

      // Fallback: match by mam_id
      if (!matchedTorrent && historyMamId) {
        matchedTorrent = torrents.find(t => String(t.mam_id || '').trim() === historyMamId);
      }

      // Populate dropdown with all torrents
      torrents.forEach(t => {
        const opt = document.createElement('option');
        opt.value = t.hash;
        opt.dataset.mamId = t.mam_id || '';
        opt.dataset.contentPath = t.content_path || t.save_path || '';

        // Mark matched torrent
        const isMatched = matchedTorrent && t.hash === matchedTorrent.hash;
        const matchSuffix = isMatched ? ' (MATCHED)' : '';
        opt.textContent = `${t.name}  —  ${t.single_file ? 'single-file' : (t.root || t.name)}${matchSuffix}`;

        if (isMatched) {
          opt.selected = true;
        }

        sel.appendChild(opt);
      });

      // Show initial status message
      if (matchedTorrent) {
        st.innerHTML = '<span style="color: #27ae60;">✓ Torrent auto-selected based on match</span>';

        // Trigger auto-detection for the matched torrent
        (async () => {
          const hash = matchedTorrent.hash;
          treeData = await fetchTreeData(hash);
          if (treeData) {
            if (treeData.recommended_flatten) {
              flattenCheckbox.checked = true;
              detectionHint.innerHTML = `<span style="color:#27ae60;">✓ Multi-disc detected (${treeData.disc_count} discs) - flatten recommended</span>`;
            } else if (treeData.single_file) {
              flattenCheckbox.checked = false;
              flattenCheckbox.disabled = true;
              detectionHint.innerHTML = '<span style="color:#999;">Single file - flatten not applicable</span>';
            } else {
              flattenCheckbox.checked = false;
              flattenCheckbox.disabled = false;
              detectionHint.textContent = '';
            }
          }
        })();
      } else if (historyHash || historyMamId) {
        st.innerHTML = '<span style="color: #f39c12;">⚠️ No matching torrent found - please select manually</span>';
      }
    } else {
      const opt = document.createElement('option');
      opt.disabled = true; opt.selected = true;
      opt.textContent = 'No completed torrents in category';
      sel.appendChild(opt);
    }
  } catch (e) {
    console.error(e);
    sel.innerHTML = '<option disabled selected>Failed to load torrents</option>';
  }

  // Function to fetch and display tree data
  async function fetchTreeData(hash) {
    try {
      const r = await fetch(`/qb/torrent/${encodeURIComponent(hash)}/tree`);
      if (!r.ok) {
        console.error('Failed to fetch tree data:', r.status);
        return null;
      }
      return await r.json();
    } catch (e) {
      console.error('Error fetching tree data:', e);
      return null;
    }
  }

  // Function to render tree view
  function renderTreeView(data, showFlattened) {
    if (!data || !data.files || data.files.length === 0) {
      return '<div style="color:#999;">No files found</div>';
    }

    const files = data.files;

    if (showFlattened && data.has_disc_structure) {
      // Show flattened preview
      let html = '<div style="margin-bottom:8px;color:#27ae60;font-weight:bold;">📁 Preview after flatten:</div>';

      // Build file structure with disc/track info
      const fileList = [];
      for (const file of files) {
        if (file.path.toLowerCase().endsWith('.cue')) continue;
        fileList.push(file);
      }

      // Sort and number them
      html += '<div style="margin-left:16px;">';
      fileList.forEach((file, idx) => {
        const ext = file.path.substring(file.path.lastIndexOf('.'));
        const newName = `Part ${String(idx + 1).padStart(3, '0')}${ext}`;
        const sizeStr = formatSize(file.size);
        html += `<div>🎵 ${escapeHtml(newName)} <span style="color:#999;font-size:0.9em;">(was: ${escapeHtml(file.path)}) - ${sizeStr}</span></div>`;
      });
      html += '</div>';

      return html;
    } else {
      // Show original structure
      let html = '<div style="margin-bottom:8px;font-weight:bold;">📁 Original structure:</div>';

      // Build hierarchical view
      const tree = {};
      for (const file of files) {
        const parts = file.path.split('/');
        let current = tree;

        for (let i = 0; i < parts.length; i++) {
          const part = parts[i];
          if (i === parts.length - 1) {
            // File
            if (!current._files) current._files = [];
            current._files.push({ name: part, size: file.size });
          } else {
            // Directory
            if (!current[part]) current[part] = {};
            current = current[part];
          }
        }
      }

      // Render tree recursively
      function renderNode(node, depth = 0) {
        let result = '';
        const indent = '  '.repeat(depth);

        // Render directories first
        for (const [key, value] of Object.entries(node)) {
          if (key === '_files') continue;
          result += `<div style="margin-left:${depth * 16}px;">📁 ${escapeHtml(key)}/</div>`;
          result += renderNode(value, depth + 1);
        }

        // Then files
        if (node._files) {
          for (const file of node._files) {
            const sizeStr = formatSize(file.size);
            result += `<div style="margin-left:${depth * 16}px;">🎵 ${escapeHtml(file.name)} <span style="color:#999;font-size:0.9em;">- ${sizeStr}</span></div>`;
          }
        }

        return result;
      }

      html += renderNode(tree);
      return html;
    }
  }

  // Add validation when user changes torrent selection
  sel.addEventListener('change', async () => {
    const selectedOption = sel.options[sel.selectedIndex];
    const selectedMamId = selectedOption?.dataset.mamId || '';
    const selectedContentPath = selectedOption?.dataset.contentPath || '';
    const historyMamId = String(h.mam_id || '').trim();
    const hash = sel.value;

    let warnings = [];

    // Check if selected torrent matches history item
    if (historyMamId && selectedMamId !== historyMamId) {
      const selectedName = selectedOption?.textContent?.split('—')[0].trim() || 'Unknown';
      warnings.push(`<span style="color: #f39c12;">⚠️ This torrent does not match the history item</span><br>
        <span style="font-size: 0.9em;">Selected: ${escapeHtml(selectedName)} | Expected: ${escapeHtml(h.title || 'Unknown')}</span>`);
    }

    // Check if torrent path seems valid (basic check - backend will validate properly)
    if (selectedContentPath && !selectedContentPath.includes('/media/')) {
      warnings.push(`<span style="color: #e74c3c;">❌ Torrent download dir does not match expected path - hardlink may fail</span>`);
    }

    if (warnings.length > 0) {
      st.innerHTML = warnings.join('<br>');
    } else if (historyMamId && selectedMamId === historyMamId) {
      st.innerHTML = '<span style="color: #27ae60;">✓ Torrent matches history item</span>';
    } else {
      st.textContent = '';
    }

    // Fetch tree data and run chapter detector
    if (hash && hash !== 'Loading torrents…') {
      treeData = await fetchTreeData(hash);

      if (treeData) {
        // Auto-check flatten if multi-disc detected
        if (treeData.recommended_flatten) {
          flattenCheckbox.checked = true;
          detectionHint.innerHTML = `<span style="color:#27ae60;">✓ Multi-disc detected (${treeData.disc_count} discs) - flatten recommended</span>`;
        } else if (treeData.single_file) {
          flattenCheckbox.checked = false;
          flattenCheckbox.disabled = true;
          detectionHint.innerHTML = '<span style="color:#999;">Single file - flatten not applicable</span>';
        } else {
          flattenCheckbox.checked = false;
          flattenCheckbox.disabled = false;
          detectionHint.textContent = '';
        }

        // Update tree view if it's already open
        if (treeView.style.display !== 'none') {
          treeView.innerHTML = renderTreeView(treeData, flattenCheckbox.checked);
        }
      }
    }
  });

  // View Files button handler
  viewFilesBtn.addEventListener('click', () => {
    if (treeView.style.display === 'none') {
      if (treeData) {
        treeView.innerHTML = renderTreeView(treeData, flattenCheckbox.checked);
        treeView.style.display = 'block';
        viewFilesBtn.textContent = '📁 Hide Files';
      } else {
        treeView.innerHTML = '<div style="color:#f39c12;">Please select a torrent first</div>';
        treeView.style.display = 'block';
        viewFilesBtn.textContent = '📁 Hide Files';
      }
    } else {
      treeView.style.display = 'none';
      viewFilesBtn.textContent = '📁 View Files';
    }
  });

  // Flatten checkbox change handler
  flattenCheckbox.addEventListener('change', () => {
    // Update tree view if it's visible
    if (treeView.style.display !== 'none' && treeData) {
      treeView.innerHTML = renderTreeView(treeData, flattenCheckbox.checked);
    }
  });

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
      const flatten = flattenCheckbox.checked;
      console.log('import payload', { author, title, hash, history_id: h.id, flatten });  // logging to troubleshoot mark-as-imported
      const r = await fetch('/import', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          author,
          title,
          hash,
          history_id: h.id,
          flatten
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

// ---------- Page Load: Restore State from URL ----------
(async () => {
  const state = getStateFromURL();

  // Pre-populate form inputs from URL
  if (state.q) {
    if (q) q.value = state.q;
  }
  if (state.sort) {
    if (sortSel) sortSel.value = state.sort;
  }
  if (state.perpage) {
    if (perpageSel) perpageSel.value = state.perpage;
  }

  // Auto-run search if query parameter exists
  if (state.q) {
    await runSearch();
  }

  // Auto-open view based on URL parameter
  if (state.view === 'history') {
    showView('history');
    await loadHistory();
  } else if (state.view === 'logs') {
    showView('logs');
    await loadLogs();
  }
})();

// ---------- Handle Browser Back/Forward Navigation ----------
window.addEventListener('popstate', async (event) => {
  const state = event.state || getStateFromURL();

  // Restore form inputs
  if (q) q.value = state.q || '';
  if (sortSel) sortSel.value = state.sort || 'default';
  if (perpageSel) perpageSel.value = state.perpage || '25';

  // Re-run search if query exists
  if (state.q) {
    await runSearch();
  } else {
    // Clear search results if no query
    table.style.display = 'none';
    tbody.innerHTML = '';
    statusEl.textContent = '';
  }

  // Switch to appropriate view based on URL
  if (state.view === 'history') {
    showView('history');
    await loadHistory();
  } else if (state.view === 'logs') {
    showView('logs');
    await loadLogs();
  } else if (state.view === '' && state.q === '') {
    showView('search');
  }
});
