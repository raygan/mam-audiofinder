/**
 * Router and URL state management for MAM Audiobook Finder
 * Handles URL query parameters, browser history, and view navigation
 */

/**
 * Router class for managing application state and navigation
 */
export class Router {
  constructor() {
    this.currentView = 'search';
    this.views = {
      search: { card: null, navBtn: 'navSearch' },
      history: { card: 'historyCard', navBtn: 'navHistory' },
      showcase: { card: 'showcaseCard', navBtn: 'navShowcase' },
      logs: { card: 'logsCard', navBtn: 'navLogs' }
    };

    // Bind popstate handler
    window.addEventListener('popstate', (e) => this.handlePopState(e));
  }

  /**
   * Extract state from URL query parameters
   * @returns {{q: string, sort: string, perpage: string, view: string}}
   */
  getStateFromURL() {
    const params = new URLSearchParams(window.location.search);
    return {
      q: params.get('q') || '',
      sort: params.get('sort') || 'default',
      perpage: params.get('perpage') || '25',
      view: params.get('view') || ''
    };
  }

  /**
   * Update URL with new state
   * @param {Object} state - State object to encode in URL
   * @param {boolean} replace - Replace current history entry instead of pushing new one
   */
  updateURL(state, replace = false) {
    const params = new URLSearchParams();

    if (state.q) params.set('q', state.q);
    if (state.sort && state.sort !== 'default') params.set('sort', state.sort);
    if (state.perpage && state.perpage !== '25') params.set('perpage', state.perpage);
    if (state.view) params.set('view', state.view);

    const newURL = params.toString()
      ? `${window.location.pathname}?${params.toString()}`
      : window.location.pathname;

    if (replace) {
      window.history.replaceState(state, '', newURL);
    } else {
      window.history.pushState(state, '', newURL);
    }
  }

  /**
   * Get current state from UI elements
   * @param {Object} elements - DOM elements containing state
   * @returns {{q: string, sort: string, perpage: string, view: string}}
   */
  getCurrentState(elements) {
    // Determine current view based on visible cards
    let currentView = '';
    if (document.getElementById('historyCard')?.style.display === '') {
      currentView = 'history';
    } else if (document.getElementById('showcaseCard')?.style.display === '') {
      currentView = 'showcase';
    } else if (document.getElementById('logsCard')?.style.display === '') {
      currentView = 'logs';
    }

    return {
      q: (elements.q?.value || '').trim(),
      sort: (elements.sort?.value) || 'default',
      perpage: (elements.perpage?.value) || '25',
      view: currentView
    };
  }

  /**
   * Handle browser back/forward navigation
   * @param {PopStateEvent} event - Browser popstate event
   */
  handlePopState(event) {
    const state = event.state || this.getStateFromURL();
    // Dispatch custom event that views can listen to
    window.dispatchEvent(new CustomEvent('routerStateChange', { detail: state }));
  }

  /**
   * Navigate to a specific view
   * @param {string} viewName - Name of view to show (search, history, showcase, logs)
   */
  navigateTo(viewName) {
    this.currentView = viewName;
    this.showView(viewName);
  }

  /**
   * Show a specific view and hide others
   * @param {string} viewName - Name of view to show
   */
  showView(viewName) {
    // Only emit event if view is actually changing
    const viewChanged = this.currentView !== viewName;
    this.currentView = viewName;

    // Update active nav button
    Object.values(this.views).forEach(view => {
      const btn = document.getElementById(view.navBtn);
      if (btn) btn.classList.remove('active');
    });

    const activeBtn = document.getElementById(this.views[viewName]?.navBtn);
    if (activeBtn) activeBtn.classList.add('active');

    // Show/hide cards
    Object.entries(this.views).forEach(([name, view]) => {
      if (view.card) {
        const card = document.getElementById(view.card);
        if (card) {
          card.style.display = (name === viewName) ? '' : 'none';
        }
      }
    });

    // Scroll to appropriate section
    if (viewName !== 'search') {
      const card = document.getElementById(this.views[viewName]?.card);
      if (card) {
        card.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    } else {
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }

    // Dispatch custom event for view lifecycle management
    window.dispatchEvent(new CustomEvent('routerViewChange', {
      detail: { view: viewName }
    }));
  }
}
