// Shared helpers for the search and wishlist pages (loaded before page scripts).

const MEDIA_BADGE = { audiobook: '🎧', ebook: '📖' };
function mediaBadge(type) {
  const icon = MEDIA_BADGE[type];
  if (!icon) return '';
  return `<span class="badge" title="${type === 'ebook' ? 'Ebook' : 'Audiobook'}">${icon}</span>`;
}

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

// "HTTP 424 — <server detail>" from a failed fetch response.
async function errorOf(r) {
  let msg = `HTTP ${r.status}`;
  try { const j = await r.json(); if (j?.detail) msg += ` — ${j.detail}`; } catch {}
  return msg;
}
