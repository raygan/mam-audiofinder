/**
 * MAM Audiobook Finder - Main Application Entry Point
 * Modular architecture with ES6 imports
 */

import { Router } from './js/core/router.js';
import { api } from './js/core/api.js';
import { SearchView } from './js/views/searchView.js';
import { HistoryView } from './js/views/historyView.js';
import { ShowcaseView } from './js/views/showcaseView.js';
import { LogsView } from './js/views/logsView.js';

/**
 * Main Application class
 */
class App {
  constructor() {
    this.router = null;
    this.views = {};
    this.elements = {};
  }

  /**
   * Initialize the application
   */
  async init() {
    // Collect DOM element references
    this.collectElements();

    // Initialize router
    this.router = new Router();

    // Initialize all views
    this.initializeViews();

    // Set up navigation handlers
    this.setupNavigation();

    // Set up router event handlers
    this.setupRouterHandlers();

    // Check application health
    await this.checkHealth();

    // Restore state from URL and initialize the appropriate view
    this.restoreStateFromURL();
  }

  /**
   * Collect DOM element references
   */
  collectElements() {
    this.elements = {
      // Search elements
      searchForm: document.getElementById('searchForm'),
      searchQ: document.getElementById('q'),
      searchSort: document.getElementById('sort'),
      searchPerpage: document.getElementById('perpage'),
      searchStatus: document.getElementById('status'),
      searchTable: document.getElementById('results'),
      searchTbody: document.querySelector('#results tbody'),

      // History elements
      historyCard: document.getElementById('historyCard'),
      historyTable: document.getElementById('history'),
      historyTbody: document.querySelector('#history tbody'),

      // Showcase elements
      showcaseCard: document.getElementById('showcaseCard'),
      showcaseSearch: document.getElementById('showcaseSearch'),
      showcaseLimit: document.getElementById('showcaseLimit'),
      showcaseSearchBtn: document.getElementById('showcaseSearchBtn'),
      showcaseStatus: document.getElementById('showcaseStatus'),
      showcaseGrid: document.getElementById('showcaseGrid'),
      showcaseDetail: document.getElementById('showcaseDetail'),

      // Logs elements
      logsCard: document.getElementById('logsCard'),
      logsContent: document.getElementById('logsContent'),
      logsContainer: document.getElementById('logsContainer'),
      logsLevel: document.getElementById('logLevel'),
      logsLines: document.getElementById('logLines'),
      logsRefreshBtn: document.getElementById('refreshLogsBtn'),
      logsAutoScroll: document.getElementById('autoScrollLogs'),

      // Navigation elements
      navSearch: document.getElementById('navSearch'),
      navHistory: document.getElementById('navHistory'),
      navShowcase: document.getElementById('navShowcase'),
      navLogs: document.getElementById('navLogs'),
      navHealth: document.getElementById('navHealth')
    };
  }

  /**
   * Initialize all view modules
   */
  initializeViews() {
    // Search view
    this.views.search = new SearchView({
      form: this.elements.searchForm,
      q: this.elements.searchQ,
      sort: this.elements.searchSort,
      perpage: this.elements.searchPerpage,
      status: this.elements.searchStatus,
      table: this.elements.searchTable,
      tbody: this.elements.searchTbody
    }, this.router);

    // History view
    this.views.history = new HistoryView({
      card: this.elements.historyCard,
      table: this.elements.historyTable,
      tbody: this.elements.historyTbody
    });

    // Showcase view
    this.views.showcase = new ShowcaseView({
      card: this.elements.showcaseCard,
      searchInput: this.elements.showcaseSearch,
      limitSelect: this.elements.showcaseLimit,
      searchBtn: this.elements.showcaseSearchBtn,
      status: this.elements.showcaseStatus,
      grid: this.elements.showcaseGrid,
      detail: this.elements.showcaseDetail
    });

    // Logs view
    this.views.logs = new LogsView({
      card: this.elements.logsCard,
      logsContent: this.elements.logsContent,
      logsContainer: this.elements.logsContainer,
      logLevel: this.elements.logsLevel,
      logLines: this.elements.logsLines,
      refreshBtn: this.elements.logsRefreshBtn,
      autoScrollLogs: this.elements.logsAutoScroll
    });
  }

  /**
   * Set up navigation button handlers
   */
  setupNavigation() {
    // Search navigation
    this.elements.navSearch?.addEventListener('click', () => {
      this.router.navigateTo('search');
      const currentState = this.router.getCurrentState(this.elements);
      this.router.updateURL({ ...currentState, view: '' }, true);
      if (this.elements.searchQ) this.elements.searchQ.focus();
    });

    // History navigation
    this.elements.navHistory?.addEventListener('click', async () => {
      this.router.navigateTo('history');
      await this.views.history.load();
      const currentState = this.router.getCurrentState(this.elements);
      this.router.updateURL({ ...currentState, view: 'history' }, true);
    });

    // Showcase navigation
    this.elements.navShowcase?.addEventListener('click', async () => {
      this.router.navigateTo('showcase');
      await this.views.showcase.load();
      const currentState = this.router.getCurrentState(this.elements);
      this.router.updateURL({ ...currentState, view: 'showcase' }, true);
    });

    // Logs navigation
    this.elements.navLogs?.addEventListener('click', async () => {
      this.router.navigateTo('logs');
      await this.views.logs.load();
      const currentState = this.router.getCurrentState(this.elements);
      this.router.updateURL({ ...currentState, view: 'logs' }, true);
    });
  }

  /**
   * Set up router event handlers for browser back/forward
   */
  setupRouterHandlers() {
    // Handle browser back/forward navigation
    window.addEventListener('routerStateChange', async (event) => {
      const state = event.detail;

      // Restore form inputs
      if (this.elements.searchQ) this.elements.searchQ.value = state.q || '';
      if (this.elements.searchSort) this.elements.searchSort.value = state.sort || 'default';
      if (this.elements.searchPerpage) this.elements.searchPerpage.value = state.perpage || '25';

      // Re-run search if query exists
      if (state.q) {
        await this.views.search.search();
      } else {
        // Clear search results if no query
        this.elements.searchTable.style.display = 'none';
        this.elements.searchTbody.innerHTML = '';
        this.elements.searchStatus.textContent = '';
      }

      // Switch to appropriate view based on URL
      if (state.view === 'history') {
        this.router.showView('history');
        await this.views.history.load();
      } else if (state.view === 'showcase') {
        this.router.showView('showcase');
        await this.views.showcase.load();
      } else if (state.view === 'logs') {
        this.router.showView('logs');
        await this.views.logs.load();
      } else if (state.view === '' && state.q === '') {
        this.router.showView('search');
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
      await this.views.search.search();
    } else if (!state.q && !state.view) {
      // Focus search box if no state to restore
      if (this.elements.searchQ) this.elements.searchQ.focus();
    }

    // Auto-open view based on URL parameter
    if (state.view === 'history') {
      this.router.showView('history');
      await this.views.history.load();
    } else if (state.view === 'showcase') {
      this.router.showView('showcase');
      await this.views.showcase.load();
    } else if (state.view === 'logs') {
      this.router.showView('logs');
      await this.views.logs.load();
    }
  }
}

// Initialize application when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => {
    window.app = new App();
    window.app.init().catch(err => {
      console.error('Failed to initialize app:', err);
    });
  });
} else {
  // DOM already loaded
  window.app = new App();
  window.app.init().catch(err => {
    console.error('Failed to initialize app:', err);
  });
}
