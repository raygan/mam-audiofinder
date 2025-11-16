/**
 * Logs Page Entry Point
 * Handles application logs viewing and filtering
 */

import { Router } from '../js/core/router.js';
import { api } from '../js/core/api.js';
import { LogsView } from '../js/views/logsView.js';

/**
 * Logs Page class
 */
class LogsPage {
  constructor() {
    this.router = null;
    this.logsView = null;
    this.elements = {};
  }

  /**
   * Initialize the logs page
   */
  async init() {
    // Collect DOM elements
    this.collectElements();

    // Initialize router
    this.router = new Router();

    // Initialize logs view
    this.logsView = new LogsView({
      card: null, // No card needed, we're on dedicated page
      logsContent: this.elements.logsContent,
      logsContainer: this.elements.logsContainer,
      logLevel: this.elements.logLevel,
      logLines: this.elements.logLines,
      refreshBtn: this.elements.refreshBtn,
      autoScrollLogs: this.elements.autoScrollLogs
    });

    // Check application health
    await this.checkHealth();

    // Load logs data
    await this.logsView.load();
  }

  /**
   * Collect DOM element references
   */
  collectElements() {
    this.elements = {
      logsContent: document.getElementById('logsContent'),
      logsContainer: document.getElementById('logsContainer'),
      logLevel: document.getElementById('logLevel'),
      logLines: document.getElementById('logLines'),
      refreshBtn: document.getElementById('refreshLogsBtn'),
      autoScrollLogs: document.getElementById('autoScrollLogs'),
      navHealth: document.getElementById('navHealth')
    };
  }

  /**
   * Check application health status
   */
  async checkHealth() {
    try {
      const health = await api.health();
      this.updateHealthIndicator(health.ok);
    } catch {
      this.updateHealthIndicator(false);
    }
  }

  /**
   * Update health indicator in navigation bar
   * @param {boolean} ok - Health status
   */
  updateHealthIndicator(ok) {
    const healthIndicator = this.elements.navHealth;
    const healthDot = healthIndicator?.querySelector('.health-dot');
    const healthText = healthIndicator?.querySelector('.health-text');

    if (healthIndicator && healthDot && healthText) {
      healthText.textContent = ok ? 'OK' : 'Error';
      if (ok) {
        healthIndicator.classList.add('ok');
        healthIndicator.classList.remove('error');
      } else {
        healthIndicator.classList.add('error');
        healthIndicator.classList.remove('ok');
      }
    }
  }
}

// Initialize page when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => {
    window.logsPage = new LogsPage();
    window.logsPage.init().catch(err => {
      console.error('Failed to initialize logs page:', err);
    });
  });
} else {
  // DOM already loaded
  window.logsPage = new LogsPage();
  window.logsPage.init().catch(err => {
    console.error('Failed to initialize logs page:', err);
  });
}
