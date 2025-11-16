/**
 * HistoryView module - Handles download history and import workflow
 */

import { api } from '../core/api.js';
import { escapeHtml } from '../core/utils.js';
import { ImportForm } from '../components/importForm.js';

/**
 * HistoryView handles the history table and import functionality
 */
export class HistoryView {
  constructor(elements) {
    this.elements = elements;
    this.importForms = new Map();
    this.refreshInterval = null;
    this.isActive = false;

    // Listen for torrent additions and import completions
    window.addEventListener('torrentAdded', () => {
      this.load();
    });

    window.addEventListener('importCompleted', (e) => {
      this.handleImportCompleted(e.detail.historyId);
    });

    // Listen for view changes to start/stop auto-refresh
    window.addEventListener('routerViewChange', (e) => {
      if (e.detail.view === 'history') {
        this.startAutoRefresh();
      } else {
        this.stopAutoRefresh();
      }
    });
  }

  /**
   * Load and display history
   */
  async load() {
    console.log('[HistoryView] load() called at', new Date().toISOString());
    try {
      const data = await api.getHistory();
      console.log('[HistoryView] Received data:', data);
      const items = data.items || [];
      console.log('[HistoryView] Items count:', items.length);

      if (items.length > 0) {
        console.log('[HistoryView] First item:', {
          title: items[0].title,
          qb_status: items[0].qb_status,
          qb_status_color: items[0].qb_status_color,
          qb_hash: items[0].qb_hash,
          qb_progress: items[0].qb_progress,
          path_warning: items[0].path_warning
        });
      }

      this.elements.tbody.innerHTML = '';

      if (!items.length) {
        this.renderEmptyState();
        this.elements.card.style.display = '';
        return;
      }

      items.forEach((item) => {
        this.createHistoryRow(item);
      });

      this.elements.card.style.display = '';
    } catch (e) {
      console.error('[HistoryView] history load failed', e);
    }
  }

  /**
   * Render empty state when no history items
   */
  renderEmptyState() {
    const colSpan = this.elements.table.querySelector('thead tr').children.length;
    const tr = document.createElement('tr');
    tr.className = 'empty';
    tr.innerHTML = `<td colspan="${colSpan}" class="center muted">No items in history yet.</td>`;
    this.elements.tbody.appendChild(tr);
  }

  /**
   * Create a history row with import functionality
   * @param {Object} h - History item data
   */
  createHistoryRow(h) {
    console.log('[HistoryView] createHistoryRow for:', {
      title: h.title,
      qb_status: h.qb_status,
      qb_status_color: h.qb_status_color,
      qb_hash: h.qb_hash
    });

    const tr = document.createElement('tr');
    const when = h.added_at ? new Date(h.added_at.replace(' ', 'T') + 'Z').toLocaleString() : '';
    const linkURL = h.mam_id ? `https://www.myanonamouse.net/t/${encodeURIComponent(h.mam_id)}` : '';

    // Create buttons
    const importBtn = document.createElement('button');
    importBtn.textContent = 'Import';

    const verifyBtn = document.createElement('button');
    verifyBtn.textContent = '🔄 Verify';
    verifyBtn.title = 'Re-check verification in Audiobookshelf';
    verifyBtn.style.display = h.imported_at ? '' : 'none';  // Only show for imported items
    verifyBtn.addEventListener('click', async () => {
      await this.verifyHistoryItem(h.id, tr);
    });

    const rmBtn = document.createElement('button');
    rmBtn.textContent = 'Remove';
    rmBtn.addEventListener('click', async () => {
      await this.removeHistoryItem(h.id, tr);
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

    console.log('[HistoryView] Status rendering:', {
      statusColor,
      statusStyle,
      qb_status: h.qb_status
    });

    // Path warning indicator
    const pathWarningIcon = h.path_warning
      ? `<span style="color: #e74c3c; cursor: help; margin-left: 4px;" title="${escapeHtml(h.path_warning)}">⚠️</span>`
      : '';

    // Verification status indicator (only show if imported)
    let verifyBadge = '';
    if (h.imported_at && h.abs_verify_status) {
      const status = h.abs_verify_status;
      const note = h.abs_verify_note || '';

      if (status === 'verified') {
        verifyBadge = `<span style="color: #27ae60; cursor: help; margin-left: 6px;" title="Verified in Audiobookshelf: ${escapeHtml(note)}">✓</span>`;
      } else if (status === 'mismatch') {
        verifyBadge = `<span style="color: #f39c12; cursor: help; margin-left: 6px;" title="Mismatch: ${escapeHtml(note)}">⚠</span>`;
      } else if (status === 'not_found') {
        verifyBadge = `<span style="color: #e74c3c; cursor: help; margin-left: 6px;" title="Not found in library: ${escapeHtml(note)}">✗</span>`;
      } else if (status === 'unreachable' || status === 'not_configured') {
        verifyBadge = `<span style="color: #999; cursor: help; margin-left: 6px;" title="${escapeHtml(note)}">?</span>`;
      }
    }

    tr.innerHTML = `
      <td style="padding: 0.25rem;">${coverHTML}</td>
      <td>${escapeHtml(h.title || '')}</td>
      <td>${escapeHtml(h.author || '')}</td>
      <td>${escapeHtml(h.narrator || '')}</td>
      <td class="center">${linkURL ? `<a href="${linkURL}" target="_blank" rel="noopener noreferrer" title="Open on MAM">🔗</a>` : ''}</td>
      <td>${escapeHtml(when)}</td>
      <td><span style="${statusStyle}">${escapeHtml(h.qb_status || '')}</span>${pathWarningIcon}${verifyBadge}</td>
      <td></td>
      <td></td>
      <td></td>
    `;

    tr.children[tr.children.length - 3].appendChild(importBtn);
    tr.children[tr.children.length - 2].appendChild(verifyBtn);
    tr.lastElementChild.appendChild(rmBtn);
    this.elements.tbody.appendChild(tr);

    // Create expander row (initially hidden)
    const expanderRow = document.createElement('tr');
    expanderRow.style.display = 'none';
    const expanderTd = document.createElement('td');
    expanderTd.colSpan = this.elements.table.querySelector('thead tr').children.length;
    expanderRow.appendChild(expanderTd);
    this.elements.tbody.appendChild(expanderRow);

    // Import button click handler
    importBtn.addEventListener('click', async () => {
      await this.toggleImportForm(h, expanderRow, importBtn);
    });
  }

  /**
   * Toggle import form visibility
   * @param {Object} historyItem - History item data
   * @param {HTMLTableRowElement} expanderRow - Expander row element
   * @param {HTMLButtonElement} importBtn - Import button element
   */
  async toggleImportForm(historyItem, expanderRow, importBtn) {
    // Toggle open/close
    if (expanderRow.style.display === '') {
      expanderRow.style.display = 'none';
      expanderRow.querySelector('td').innerHTML = '';
      return;
    }

    expanderRow.style.display = '';

    // Create and render import form
    const importForm = new ImportForm(historyItem, expanderRow, this.elements.table);
    this.importForms.set(historyItem.id, importForm);
    await importForm.render();
  }

  /**
   * Remove a history item
   * @param {number} id - History item ID
   * @param {HTMLTableRowElement} tr - Table row element
   */
  async removeHistoryItem(id, tr) {
    const rmBtn = tr.querySelector('button:last-child');
    rmBtn.disabled = true;

    try {
      await api.deleteHistoryItem(id);

      // Remove the row and its expander
      const nextRow = tr.nextElementSibling;
      if (nextRow && nextRow.querySelector('td').colSpan > 1) {
        nextRow.remove();
      }
      tr.remove();

      // Remove from import forms map
      this.importForms.delete(id);

      // If we just removed the last row, render the empty state
      if (!this.elements.tbody.children.length) {
        this.renderEmptyState();
      }
    } catch (e) {
      console.error('remove failed', e);
      rmBtn.disabled = false;
    }
  }

  /**
   * Manually verify a history item
   * @param {number} id - History item ID
   * @param {HTMLTableRowElement} tr - Table row element
   */
  async verifyHistoryItem(id, tr) {
    // Find the verify button (second to last button)
    const buttons = tr.querySelectorAll('button');
    const verifyBtn = buttons[buttons.length - 2];
    const originalText = verifyBtn.textContent;

    verifyBtn.disabled = true;
    verifyBtn.textContent = '⏳ Verifying...';

    try {
      const result = await api.verifyHistoryItem(id);

      if (result.ok && result.verification) {
        // Update the status column with new verification badge
        const statusCell = tr.children[6];  // Status column
        const status = result.verification.status;
        const note = result.verification.note || '';

        // Remove existing verify badge
        const existingBadge = statusCell.querySelector('span[title^="Verified"], span[title^="Mismatch"], span[title^="Not found"]');
        if (existingBadge) {
          existingBadge.remove();
        }

        // Add new verify badge
        let verifyBadge = '';
        if (status === 'verified') {
          verifyBadge = `<span style="color: #27ae60; cursor: help; margin-left: 6px;" title="Verified in Audiobookshelf: ${escapeHtml(note)}">✓</span>`;
        } else if (status === 'mismatch') {
          verifyBadge = `<span style="color: #f39c12; cursor: help; margin-left: 6px;" title="Mismatch: ${escapeHtml(note)}">⚠</span>`;
        } else if (status === 'not_found') {
          verifyBadge = `<span style="color: #e74c3c; cursor: help; margin-left: 6px;" title="Not found in library: ${escapeHtml(note)}">✗</span>`;
        } else if (status === 'unreachable' || status === 'not_configured') {
          verifyBadge = `<span style="color: #999; cursor: help; margin-left: 6px;" title="${escapeHtml(note)}">?</span>`;
        }

        if (verifyBadge) {
          statusCell.insertAdjacentHTML('beforeend', verifyBadge);
        }

        verifyBtn.textContent = '✓ Done';
        setTimeout(() => {
          verifyBtn.textContent = originalText;
          verifyBtn.disabled = false;
        }, 2000);
      } else {
        verifyBtn.textContent = '✗ Failed';
        setTimeout(() => {
          verifyBtn.textContent = originalText;
          verifyBtn.disabled = false;
        }, 2000);
      }
    } catch (e) {
      console.error('verify failed', e);
      verifyBtn.textContent = '✗ Error';
      setTimeout(() => {
        verifyBtn.textContent = originalText;
        verifyBtn.disabled = false;
      }, 2000);
    }
  }

  /**
   * Handle import completion
   * @param {number} historyId - History item ID
   */
  handleImportCompleted(historyId) {
    // Find the row and update its status
    const rows = this.elements.tbody.querySelectorAll('tr');
    for (let i = 0; i < rows.length; i++) {
      const row = rows[i];
      if (row.classList.contains('empty')) continue;

      // Check if this is the matching history row
      // We can identify it by checking if the import form is in our map
      if (this.importForms.has(historyId)) {
        // Update the status column (index 6)
        const statusTd = row.children[6];
        if (statusTd) {
          statusTd.innerHTML = '<span style="color: #27ae60; font-weight: 500;">imported</span>';
        }
        break;
      }
    }
  }

  /**
   * Start auto-refreshing the history view to show live torrent states
   */
  startAutoRefresh() {
    console.log('[HistoryView] startAutoRefresh() called');
    this.isActive = true;

    // Clear any existing interval
    this.stopAutoRefresh();

    // Refresh every 5 seconds to show live download progress
    this.refreshInterval = setInterval(() => {
      if (this.isActive) {
        console.log('[HistoryView] Auto-refresh tick - calling load()');
        this.load();
      }
    }, 5000);
    console.log('[HistoryView] Auto-refresh started with interval:', this.refreshInterval);
  }

  /**
   * Stop auto-refreshing when view is not active
   */
  stopAutoRefresh() {
    console.log('[HistoryView] stopAutoRefresh() called, isActive:', this.isActive, 'interval:', this.refreshInterval);
    this.isActive = false;

    if (this.refreshInterval) {
      clearInterval(this.refreshInterval);
      this.refreshInterval = null;
      console.log('[HistoryView] Auto-refresh stopped');
    }
  }
}
