/**
 * History Page Entry Point
 * Handles history view, imports, and torrent tracking
 */

import { Router } from '../js/core/router.js';
import { api } from '../js/core/api.js';
import { HistoryView } from '../js/views/historyView.js';

/**
 * History Page class
 */
class HistoryPage {
  constructor() {
    this.router = null;
    this.historyView = null;
    this.elements = {};
  }

  /**
   * Initialize the history page
   */
  async init() {
    // Collect DOM elements
    this.collectElements();

    // Initialize router
    this.router = new Router();

    // Initialize history view
    this.historyView = new HistoryView({
      card: null, // No card needed, we're on dedicated page
      table: this.elements.historyTable,
      tbody: this.elements.historyTbody
    });

    // Check application health
    await this.checkHealth();

    // Load history data
    await this.historyView.load();
  }

  /**
   * Collect DOM element references
   */
  collectElements() {
    this.elements = {
      historyTable: document.getElementById('history'),
      historyTbody: document.querySelector('#history tbody'),
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
    window.historyPage = new HistoryPage();
    window.historyPage.init().catch(err => {
      console.error('Failed to initialize history page:', err);
    });
  });
} else {
  // DOM already loaded
  window.historyPage = new HistoryPage();
  window.historyPage.init().catch(err => {
    console.error('Failed to initialize history page:', err);
  });
}
