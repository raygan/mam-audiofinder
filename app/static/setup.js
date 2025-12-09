// Simple first-run setup helper

async function runHealthCheck() {
  const healthEl = document.getElementById('health');
  if (!healthEl) return;
  try {
    const r = await fetch('/health');
    const j = await r.json();
    healthEl.textContent = j.ok ? 'OK' : 'Not OK';
  } catch {
    healthEl.textContent = 'Error';
  }
}

document.addEventListener('DOMContentLoaded', () => {
  runHealthCheck();

  const form = document.getElementById('setupForm');
  const statusEl = document.getElementById('setupStatus');
  if (!form) return;

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const body = {
      mam_cookie: document.getElementById('mam_cookie')?.value.trim() || '',
      qb_url: document.getElementById('qb_url')?.value.trim() || '',
      qb_user: document.getElementById('qb_user')?.value.trim() || '',
      qb_pass: document.getElementById('qb_pass')?.value || '',
      qb_prefix: document.getElementById('qb_prefix')?.value.trim() || '',
      app_prefix: document.getElementById('app_prefix')?.value.trim() || '',
      lib_dir: document.getElementById('lib_dir')?.value.trim() || '',
    };

    statusEl.textContent = 'Saving…';

    try {
      const resp = await fetch('/api/setup', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!resp.ok) {
        let msg = `HTTP ${resp.status}`;
        try {
          const j = await resp.json();
          if (j?.detail) msg += ` — ${j.detail}`;
        } catch {}
        throw new Error(msg);
      }
      statusEl.textContent = 'Saved. You can now go back to the main app.';
    } catch (e) {
      console.error('setup save failed', e);
      statusEl.textContent = `Failed to save: ${e.message || e}`;
    }
  });
});

