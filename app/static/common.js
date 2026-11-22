// Shared helpers for the search and wishlist pages (loaded before page scripts).

const MEDIA_BADGE = { audiobook: '🎧', ebook: '📖' };
function mediaBadge(type) {
  const icon = MEDIA_BADGE[type];
  if (!icon) return '';
  return `<span class="badge" title="${type === 'ebook' ? 'Ebook' : 'Audiobook'}">${icon}</span>`;
}

// Safe for text and for attribute values (titles can contain quotes).
function escapeHtml(s) {
  return (s ?? '').toString()
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
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

// ---------- Light / dark ----------
// "auto" follows the system; the choice is per browser. The <head> applies
// it before the page paints, so there's no flash.
const THEME_KEY = 'bookfinder.theme';
const THEME_ICONS = { auto: '🌓', light: '☀️', dark: '🌙' };
const THEME_NAMES = { auto: 'Theme: follow system', light: 'Theme: light', dark: 'Theme: dark' };

function currentTheme() {
  try { const t = localStorage.getItem(THEME_KEY); return t === 'light' || t === 'dark' ? t : 'auto'; }
  catch { return 'auto'; }
}

function applyTheme(t) {
  if (t === 'auto') delete document.documentElement.dataset.theme;
  else document.documentElement.dataset.theme = t;
  const btn = document.getElementById('themeToggle');
  if (btn) { btn.textContent = THEME_ICONS[t]; btn.title = THEME_NAMES[t]; btn.setAttribute('aria-label', THEME_NAMES[t]); }
}

document.addEventListener('DOMContentLoaded', () => {
  applyTheme(currentTheme());
  document.getElementById('themeToggle')?.addEventListener('click', () => {
    const next = { auto: 'light', light: 'dark', dark: 'auto' }[currentTheme()];
    try { if (next === 'auto') localStorage.removeItem(THEME_KEY); else localStorage.setItem(THEME_KEY, next); } catch {}
    applyTheme(next);
  });
});
