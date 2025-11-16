/**
 * Router and URL state management for MAM Audiobook Finder
 * Handles URL query parameters, browser history, and page navigation
 * Updated for multi-page architecture
 */

/**
 * Router class for managing application state and navigation
 */
export class Router {
  constructor() {
    // Bind popstate handler
    window.addEventListener('popstate', (e) => this.handlePopState(e));
  }

  /**
   * Extract state from URL query parameters
   * @returns {Object} State object with all URL parameters
   */
  getStateFromURL() {
    const params = new URLSearchParams(window.location.search);
    const state = {};

    // Convert all URL params to state object
    for (const [key, value] of params.entries()) {
      state[key] = value;
    }

    return state;
  }

  /**
   * Update URL with new state
   * @param {Object} state - State object to encode in URL
   * @param {boolean} replace - Replace current history entry instead of pushing new one
   */
  updateURL(state, replace = false) {
    const params = new URLSearchParams();

    // Add all non-empty state values to URL params
    Object.entries(state).forEach(([key, value]) => {
      if (value && value !== '' && value !== 'default' && value !== '25') {
        params.set(key, value);
      }
    });

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
   * @returns {Object} Current state from form inputs
   */
  getCurrentState(elements) {
    const state = {};

    // Collect state from any provided elements
    if (elements.q) state.q = elements.q.value?.trim() || '';
    if (elements.sort) state.sort = elements.sort.value || 'default';
    if (elements.perpage) state.perpage = elements.perpage.value || '25';
    if (elements.showcaseSearch) state.q = elements.showcaseSearch.value?.trim() || '';
    if (elements.showcaseLimit) state.limit = elements.showcaseLimit.value || '100';

    return state;
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
   * Navigate to a specific page with optional parameters
   * @param {string} path - Path to navigate to (e.g., '/history', '/showcase')
   * @param {Object} params - Optional query parameters
   */
  navigateTo(path, params = {}) {
    const queryString = new URLSearchParams(params).toString();
    const url = queryString ? `${path}?${queryString}` : path;
    window.location.href = url;
  }

  /**
   * Build URL with parameters for navigation
   * @param {string} path - Base path
   * @param {Object} params - Query parameters
   * @returns {string} Complete URL with query string
   */
  buildURL(path, params = {}) {
    const filteredParams = {};

    // Filter out empty/default values
    Object.entries(params).forEach(([key, value]) => {
      if (value && value !== '' && value !== 'default' && value !== '25') {
        filteredParams[key] = value;
      }
    });

    const queryString = new URLSearchParams(filteredParams).toString();
    return queryString ? `${path}?${queryString}` : path;
  }
}
