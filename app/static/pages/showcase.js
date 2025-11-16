/**
 * Showcase Page Entry Point
 * Handles showcase grid view with URL parameter support
 */

import { Router } from '../js/core/router.js';
import { api } from '../js/core/api.js';
import { ShowcaseView } from '../js/views/showcaseView.js';

/**
 * Showcase Page class
 */
class ShowcasePage {
  constructor() {
    this.router = null;
    this.showcaseView = null;
    this.elements = {};
  }

  /**
   * Initialize the showcase page
   */
  async init() {
    // Collect DOM elements
    this.collectElements();

    // Initialize router
    this.router = new Router();

    // Initialize showcase view
    this.showcaseView = new ShowcaseView({
      card: null, // No card needed, we're on dedicated page
      searchInput: this.elements.showcaseSearch,
      limitSelect: this.elements.showcaseLimit,
      searchBtn: this.elements.showcaseSearchBtn,
      status: this.elements.showcaseStatus,
      grid: this.elements.showcaseGrid,
      detail: this.elements.showcaseDetail
    }, this.router);

    // Set up router event handlers
    this.setupRouterHandlers();

    // Check application health
    await this.checkHealth();

    // Restore state from URL and load data
    await this.restoreStateFromURL();
  }

  /**
   * Collect DOM element references
   */
  collectElements() {
    this.elements = {
      showcaseSearch: document.getElementById('showcaseSearch'),
      showcaseLimit: document.getElementById('showcaseLimit'),
      showcaseSearchBtn: document.getElementById('showcaseSearchBtn'),
      showcaseStatus: document.getElementById('showcaseStatus'),
      showcaseGrid: document.getElementById('showcaseGrid'),
      showcaseDetail: document.getElementById('showcaseDetail'),
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
      if (state.q && this.elements.showcaseSearch) {
        this.elements.showcaseSearch.value = state.q;
      }
      if (state.limit && this.elements.showcaseLimit) {
        this.elements.showcaseLimit.value = state.limit;
      }

      // Handle detail view state
      if (state.detail) {
        // Detail parameter exists - show detail view
        // First ensure data is loaded
        if (this.showcaseView.currentGroups.length === 0 && state.q) {
          await this.showcaseView.load();
        }
        // Then show detail
        this.showcaseView.showDetailByIdentifier(state.detail);
      } else {
        // No detail parameter - close detail view if open
        if (this.showcaseView.currentDetailGroup) {
          this.showcaseView.closeDetail(false); // Don't update history, we're already in the right state
        } else if (state.q) {
          // Reload showcase data if we have a query
          await this.showcaseView.load();
        }
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

    // Pre-populate search input from URL
    if (state.q && this.elements.showcaseSearch) {
      this.elements.showcaseSearch.value = state.q;
    }

    // Pre-populate limit from URL
    if (state.limit && this.elements.showcaseLimit) {
      this.elements.showcaseLimit.value = state.limit;
    }

    // Only load showcase data if there's a query or detail parameter
    // This prevents empty MAM searches on initial page load
    if (state.q || state.detail) {
      await this.showcaseView.load();

      // If detail parameter exists, show detail view after loading
      if (state.detail) {
        // Small delay to ensure grid is rendered
        setTimeout(() => {
          this.showcaseView.showDetailByIdentifier(state.detail);
        }, 100);
      }
    } else {
      // Show welcome message for empty state
      this.showcaseView.showEmptyState();
    }
  }
}

// Initialize page when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => {
    window.showcasePage = new ShowcasePage();
    window.showcasePage.init().catch(err => {
      console.error('Failed to initialize showcase page:', err);
    });
  });
} else {
  // DOM already loaded
  window.showcasePage = new ShowcasePage();
  window.showcasePage.init().catch(err => {
    console.error('Failed to initialize showcase page:', err);
  });
}
