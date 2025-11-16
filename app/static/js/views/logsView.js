/**
 * LogsView module - Handles application logs display
 */

import { api } from '../core/api.js';
import { escapeHtml } from '../core/utils.js';

/**
 * LogsView handles the logs viewer interface
 */
export class LogsView {
  constructor(elements) {
    this.elements = elements;
    this.bindEvents();
  }

  /**
   * Bind event listeners
   */
  bindEvents() {
    // Refresh button
    this.elements.refreshBtn?.addEventListener('click', async () => {
      await this.load();
    });

    // Log level filter
    this.elements.logLevel?.addEventListener('change', async () => {
      await this.load();
    });

    // Log lines limit
    this.elements.logLines?.addEventListener('change', async () => {
      await this.load();
    });
  }

  /**
   * Load and display logs
   */
  async load() {
    const logsContent = this.elements.logsContent;
    const logLevel = this.elements.logLevel?.value || '';
    const logLines = parseInt(this.elements.logLines?.value || '100', 10);
    const autoScroll = this.elements.autoScrollLogs?.checked;

    if (!logsContent) return;

    try {
      logsContent.textContent = 'Loading logs...';

      const data = await api.getLogs({
        lines: logLines,
        level: logLevel
      });

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
      logsContent.innerHTML = this.highlightLogs(logsText);

      // Auto-scroll to bottom if enabled
      if (autoScroll) {
        const container = this.elements.logsContainer;
        if (container) {
          container.scrollTop = container.scrollHeight;
        }
      }

    } catch (error) {
      console.error('Error loading logs:', error);
      logsContent.textContent = `Error loading logs: ${error.message}`;
    }
  }

  /**
   * Apply syntax highlighting to log text
   * @param {string} text - Raw log text
   * @returns {string} HTML with highlighted log levels
   */
  highlightLogs(text) {
    return escapeHtml(text)
      .replace(/\b(INFO)\b/g, '<span class="log-info">$1</span>')
      .replace(/\b(WARNING)\b/g, '<span class="log-warning">$1</span>')
      .replace(/\b(ERROR)\b/g, '<span class="log-error">$1</span>');
  }
}
