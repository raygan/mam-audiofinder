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
      ebook_ingest_dir: document.getElementById('ebook_ingest_dir')?.value.trim() || '',
      notify_webhook_url: document.getElementById('notify_webhook_url')?.value.trim() ?? '',
      notify_format: document.getElementById('notify_format')?.value || 'ntfy',
      notify_token: document.getElementById('notify_token')?.value || '',
      notify_clear_token: !!document.getElementById('notify_clear_token')?.checked,
      notify_click_url: document.getElementById('notify_click_url')?.value.trim() ?? '',
      notify_on_import: !!document.getElementById('notify_on_import')?.checked,
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


// "Send test notification": save the form first, then ask the server to send one.
document.addEventListener('DOMContentLoaded', () => {
  const btn = document.getElementById('notifyTestBtn');
  const st = document.getElementById('notifyTestStatus');
  const form = document.getElementById('setupForm');
  if (!btn || !form) return;
  btn.addEventListener('click', async () => {
    btn.disabled = true;
    st.textContent = 'Saving…';
    form.requestSubmit();
    // Wait for the save handler to finish (it reports in #setupStatus).
    const saved = document.getElementById('setupStatus');
    for (let i = 0; i < 50 && saved.textContent === 'Saving…'; i++) await new Promise(r => setTimeout(r, 100));
    if (!saved.textContent.startsWith('Saved')) { st.textContent = 'Fix the setup error first.'; btn.disabled = false; return; }
    st.textContent = 'Sending…';
    try {
      const r = await fetch('/api/notify/test', { method: 'POST' });
      if (!r.ok) {
        let msg = `HTTP ${r.status}`;
        try { const j = await r.json(); if (j?.detail) msg += ` — ${j.detail}`; } catch {}
        throw new Error(msg);
      }
      st.textContent = 'Sent. Check your phone.';
    } catch (e) {
      st.textContent = `Not sent: ${e.message}`;
    }
    btn.disabled = false;
  });
});
