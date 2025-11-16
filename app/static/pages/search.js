/**
 * Search Page Entry Point
 * Handles search functionality and URL parameter restoration
 */

import { Router } from '../js/core/router.js';
import { api } from '../js/core/api.js';
import { SearchView } from '../js/views/searchView.js';

/**
 * Search Page class
 */
class SearchPage {
  constructor() {
    this.router = null;
    this.searchView = null;
    this.elements = {};
  }

  /**
   * Initialize the search page
   */
  async init() {
    // Collect DOM elements
    this.collectElements();

    // Initialize router
    this.router = new Router();

    // Initialize search view
    this.searchView = new SearchView({
      form: this.elements.searchForm,
      q: this.elements.searchQ,
      sort: this.elements.searchSort,
      perpage: this.elements.searchPerpage,
      status: this.elements.searchStatus,
      table: this.elements.searchTable,
      tbody: this.elements.searchTbody
    }, this.router);

    // Set up router event handlers
    this.setupRouterHandlers();

    // Check application health
    await this.checkHealth();

    // Restore state from URL and auto-search if needed
    await this.restoreStateFromURL();
  }

  /**
   * Collect DOM element references
   */
  collectElements() {
    this.elements = {
      searchForm: document.getElementById('searchForm'),
      searchQ: document.getElementById('q'),
      searchSort: document.getElementById('sort'),
      searchPerpage: document.getElementById('perpage'),
      searchStatus: document.getElementById('status'),
      searchTable: document.getElementById('results'),
      searchTbody: document.querySelector('#results tbody'),
      navHealth: document.getElementById('navHealth')
    };
  }

  /**
   * Set up router event handlers for browser back/forward
   */
  setupRouterHandlers() {
    window.addEventListener('routerStateChange', async (event) => {
      const state = event.detail;

      // Restore form inputs
      if (this.elements.searchQ) this.elements.searchQ.value = state.q || '';
      if (this.elements.searchSort) this.elements.searchSort.value = state.sort || 'default';
      if (this.elements.searchPerpage) this.elements.searchPerpage.value = state.perpage || '25';

      // Re-run search if query exists
      if (state.q) {
        await this.searchView.search();
      } else {
        // Clear search results if no query
        this.elements.searchTable.style.display = 'none';
        this.elements.searchTbody.innerHTML = '';
        this.elements.searchStatus.textContent = '';
      }
    });
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

  /**
   * Restore application state from URL parameters
   */
  async restoreStateFromURL() {
    const state = this.router.getStateFromURL();

    // Pre-populate form inputs from URL
    if (state.q && this.elements.searchQ) {
      this.elements.searchQ.value = state.q;
    }
    if (state.sort && this.elements.searchSort) {
      this.elements.searchSort.value = state.sort;
    }
    if (state.perpage && this.elements.searchPerpage) {
      this.elements.searchPerpage.value = state.perpage;
    }

    // Auto-run search if query parameter exists
    if (state.q) {
      await this.searchView.search();
    } else {
      // Focus search box if no state to restore
      if (this.elements.searchQ) this.elements.searchQ.focus();
    }
  }
}

// Initialize page when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => {
    window.searchPage = new SearchPage();
    window.searchPage.init().catch(err => {
      console.error('Failed to initialize search page:', err);
    });
  });
} else {
  // DOM already loaded
  window.searchPage = new SearchPage();
  window.searchPage.init().catch(err => {
    console.error('Failed to initialize search page:', err);
  });
}
