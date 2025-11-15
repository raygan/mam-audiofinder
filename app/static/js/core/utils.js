/**
 * Core utility functions for the MAM Audiobook Finder frontend
 */

/**
 * Escapes HTML special characters to prevent XSS
 * @param {string} s - String to escape
 * @returns {string} Escaped string
 */
export function escapeHtml(s) {
  return (s || '').toString()
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;');
}

/**
 * Formats byte size to human-readable format
 * @param {number|string} sz - Size in bytes
 * @returns {string} Formatted size string (e.g., "1.5 GB")
 */
export function formatSize(sz) {
  if (sz == null || sz === '') return '';
  const n = Number(sz);
  if (!Number.isFinite(n)) return String(sz);
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  let i = 0, x = n;
  while (x >= 1024 && i < units.length - 1) {
    x /= 1024;
    i++;
  }
  return `${x.toFixed(1)} ${units[i]}`;
}
