// Wishlist page: saved MAM searches, manual "check now", match review.
// Only "Check now" contacts MAM (through the server's rate-limited path);
// everything else reads or changes the app's own database.

const itemsEl = document.getElementById('items');
const statusEl = document.getElementById('status');

// Small DOM builder; children are nodes or strings (strings become text, never HTML).
function el(tag, attrs = {}, ...children) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v == null || v === false) continue;
    if (k === 'class') n.className = v;
    else if (k.startsWith('on')) n.addEventListener(k.slice(2), v);
    else n.setAttribute(k, v === true ? '' : v);
  }
  for (const c of children.flat()) {
    if (c == null || c === false) continue;
    n.append(c instanceof Node ? c : String(c));
  }
  return n;
}

function when(s) {
  if (!s) return 'never';
  const d = new Date(s.replace(' ', 'T') + 'Z');
  return Number.isNaN(d.getTime()) ? s : d.toLocaleString();
}

function badges(media) {
  const span = el('span');
  span.innerHTML = media === 'both' ? mediaBadge('audiobook') + mediaBadge('ebook') : mediaBadge(media);
  return span;
}

async function api(method, url, body) {
  const r = await fetch(url, {
    method,
    headers: body ? { 'Content-Type': 'application/json' } : {},
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!r.ok) {
    const err = new Error(await errorOf(r));
    err.status = r.status;
    throw err;
  }
  return r.json();
}

// ---------------- list ----------------
async function load() {
  try {
    const [list, summary] = await Promise.all([api('GET', '/wishlist'), api('GET', '/wishlist/summary')]);
    document.getElementById('usage').textContent =
      `Wishlist searches in the last 24 hours: ${list.requests_last_24h} of ${list.max_requests_per_day}.`;
    document.getElementById('scheduler').textContent =
      summary.scheduler === 'disabled' ? 'Automatic re-checks are off.' : `Scheduler: ${summary.scheduler}.`;
    itemsEl.innerHTML = '';
    if (!list.items.length) {
      itemsEl.append(el('p', { class: 'muted' },
        'Nothing saved yet. Search for a book, then press ☆ Save (or “Save to wishlist” when there are no results).'));
      return;
    }
    list.items.forEach(item => itemsEl.append(renderItem(item)));
  } catch (e) {
    console.error(e);
    statusEl.textContent = `Couldn't load the wishlist: ${e.message}`;
  }
}

function filterSummary(f) {
  const parts = [];
  if (f.formats?.length) parts.push(`formats ${f.formats.join(', ')}`);
  if (f.min_seeders) parts.push(`≥ ${f.min_seeders} seeders`);
  if (f.exclude?.length) parts.push(`excluding ${f.exclude.join(', ')}`);
  if (f.lang_code) parts.push(`language ${f.lang_code}`);
  return parts.join(' · ');
}

function renderItem(item) {
  const card = el('div', { class: 'card', 'data-id': item.id });
  const errorLine = el('div', { class: 'error' }, item.last_error ? `Last check failed: ${item.last_error}` : '');
  const matchesBox = el('div', { class: 'matches', style: 'display:none' });
  const editBox = el('div', { style: 'display:none' });

  const title = item.label || item.query;
  const fulfilled = item.fulfilled?.length ? ` · got ${item.fulfilled.join(' + ')}` : '';
  // (native append prints null as text, so drop the optional lines first)
  card.append(...[
    el('div', { class: 'card-head' },
      badges(item.media),
      el('span', { class: 'title' }, title),
      el('span', { class: `pill ${item.status}` }, item.status),
      item.mode === 'auto' ? el('span', { class: 'pill', title: 'Auto-grab runs only with the scheduler' }, 'auto') : null,
    ),
    item.label ? el('div', { class: 'muted' }, `Search: ${item.query}`) : null,
    el('div', { class: 'muted' },
      `Saved ${when(item.created_at)} · last checked ${when(item.last_checked_at)}${fulfilled}`),
    filterSummary(item.filters) ? el('div', { class: 'muted' }, `Filters: ${filterSummary(item.filters)}`) : null,
    errorLine,
  ].filter(Boolean));

  const checkBtn = el('button', { disabled: item.status === 'done' }, 'Check now');
  checkBtn.addEventListener('click', async () => {
    checkBtn.disabled = true;
    checkBtn.textContent = 'Checking…';
    try {
      const res = await api('POST', `/wishlist/${item.id}/check`);
      const n = res.new_matches.length;
      statusEl.textContent = `${title}: ${n ? `${n} new match${n === 1 ? '' : 'es'}` : 'no new matches'}.`;
      await load();
      if (n) document.querySelector(`.card[data-id="${item.id}"] .show-matches`)?.click();
    } catch (e) {
      errorLine.textContent = e.message;
      checkBtn.disabled = false;
      checkBtn.textContent = 'Check now';
    }
  });

  const matchesBtn = el('button', { class: 'show-matches', disabled: !item.match_count },
    `Matches (${item.match_count})`);
  matchesBtn.addEventListener('click', async () => {
    if (matchesBox.style.display === '') { matchesBox.style.display = 'none'; return; }
    matchesBox.style.display = '';
    await renderMatches(item, matchesBox);
  });

  const pauseBtn = el('button', { disabled: item.status === 'done' }, item.status === 'paused' ? 'Resume' : 'Pause');
  pauseBtn.addEventListener('click', () => patch(item, { status: item.status === 'paused' ? 'active' : 'paused' }));

  const doneBtn = el('button', {}, item.status === 'done' ? 'Reactivate' : 'Mark done');
  doneBtn.addEventListener('click', () => patch(item, { status: item.status === 'done' ? 'active' : 'done' }));

  const editBtn = el('button', {}, 'Edit');
  editBtn.addEventListener('click', () => {
    if (editBox.style.display === '') { editBox.style.display = 'none'; return; }
    editBox.style.display = '';
    renderEdit(item, editBox);
  });

  const delBtn = el('button', {}, 'Delete');
  delBtn.addEventListener('click', async () => {
    if (!confirm(`Delete “${title}” from the wishlist?`)) return;
    try { await api('DELETE', `/wishlist/${item.id}`); await load(); }
    catch (e) { errorLine.textContent = e.message; }
  });

  card.append(el('div', { class: 'actions' }, checkBtn, matchesBtn, pauseBtn, doneBtn, editBtn, delBtn), editBox, matchesBox);
  return card;
}

async function patch(item, fields) {
  try { await api('PATCH', `/wishlist/${item.id}`, fields); await load(); }
  catch (e) { statusEl.textContent = e.message; }
}

// ---------------- matches ----------------
async function renderMatches(item, box) {
  box.textContent = 'Loading…';
  try {
    const { matches } = await api('GET', `/wishlist/${item.id}/matches`);
    box.innerHTML = '';
    if (!matches.length) { box.textContent = 'No matches to review.'; return; }
    matches.forEach(m => box.append(renderMatch(item, m)));
  } catch (e) {
    box.textContent = `Couldn't load matches: ${e.message}`;
  }
}

function renderMatch(item, m) {
  const r = m.result || {};
  const msg = el('span', { class: 'muted' });
  const addBtn = el('button', {}, 'Add');
  addBtn.addEventListener('click', async () => {
    addBtn.disabled = true;
    addBtn.textContent = 'Adding…';
    try {
      const resp = await fetch('/add', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          id: String(r.id || m.mam_id), title: r.title || '', dl: r.dl || '',
          author: r.author_info || '', narrator: r.narrator_info || '',
          media_type: r.media_type || 'audiobook', wishlist_id: item.id,
        }),
      });
      if (resp.status === 409) { addBtn.textContent = 'Already in qB'; return; }
      if (!resp.ok) throw new Error(await errorOf(resp));
      statusEl.textContent = `Added “${r.title}” to qBittorrent.`;
      await load();
    } catch (e) {
      msg.textContent = e.message;
      addBtn.disabled = false;
      addBtn.textContent = 'Add';
    }
  });
  const dismissBtn = el('button', { title: 'Hide this match' }, 'Dismiss');
  dismissBtn.addEventListener('click', async () => {
    try { await api('POST', `/wishlist/${item.id}/matches/${encodeURIComponent(m.mam_id)}/dismiss`); await load(); }
    catch (e) { msg.textContent = e.message; }
  });
  const link = el('a', { href: `https://www.myanonamouse.net/t/${encodeURIComponent(m.mam_id)}`,
                         target: '_blank', rel: 'noopener noreferrer', title: 'Open on MAM' }, '🔗');
  const titleBox = el('span', { class: 'm-title' });
  titleBox.innerHTML = mediaBadge(r.media_type);
  titleBox.append(r.title || `Torrent ${m.mam_id}`, r.series ? el('span', { class: 'muted' }, ` · ${r.series}`) : '');
  return el('div', { class: 'match' },
    titleBox,
    el('span', {}, [r.format, formatSize(r.size), `${r.seeders ?? '-'} seeders`].filter(Boolean).join(' · ')),
    el('span', { class: 'muted' }, `found ${when(m.first_seen_at)}`),
    link, addBtn, dismissBtn, msg);
}

// ---------------- edit ----------------
function renderEdit(item, box) {
  const f = item.filters || {};
  const v = (x) => (x == null ? '' : String(x));
  const inputs = {
    label: el('input', { type: 'text', value: v(item.label), placeholder: 'Optional friendly name' }),
    query: el('input', { type: 'text', value: item.query }),
    mode: el('select', {}, el('option', { value: 'notify' }, 'Notify me'), el('option', { value: 'auto' }, 'Auto-grab (with scheduler)')),
    interval: el('input', { type: 'number', min: '1', value: v(item.check_interval_hours), placeholder: 'Default' }),
    formats: el('input', { type: 'text', value: (f.formats || []).join(', '), placeholder: 'e.g. epub, m4b (any if empty)' }),
    min_seeders: el('input', { type: 'number', min: '0', value: v(f.min_seeders), placeholder: '0' }),
    exclude: el('input', { type: 'text', value: (f.exclude || []).join(', '), placeholder: 'words to skip, e.g. abridged' }),
    lang_code: el('input', { type: 'text', value: v(f.lang_code), placeholder: 'e.g. ENG (any if empty)', size: '6' }),
  };
  inputs.mode.value = item.mode;
  const msg = el('span', { class: 'error' });
  const list = (s) => s.split(',').map(x => x.trim()).filter(Boolean);
  const save = el('button', {}, 'Save');
  save.addEventListener('click', async () => {
    try {
      await api('PATCH', `/wishlist/${item.id}`, {
        label: inputs.label.value,
        query: inputs.query.value,
        mode: inputs.mode.value,
        check_interval_hours: inputs.interval.value ? Number(inputs.interval.value) : null,
        filters: {
          formats: list(inputs.formats.value),
          min_seeders: inputs.min_seeders.value ? Number(inputs.min_seeders.value) : 0,
          exclude: list(inputs.exclude.value),
          lang_code: inputs.lang_code.value.trim(),
        },
      });
      await load();
    } catch (e) { msg.textContent = e.message; }
  });
  const row = (label, input) => [el('label', {}, label), input];
  box.innerHTML = '';
  box.append(el('div', { class: 'edit' },
    row('Label', inputs.label), row('Search text', inputs.query), row('When found', inputs.mode),
    row('Check every (hours)', inputs.interval), row('Formats', inputs.formats),
    row('Min seeders', inputs.min_seeders), row('Exclude words', inputs.exclude), row('Language', inputs.lang_code),
    el('span'), el('span', {}, save, ' ', msg)));
}

load();
