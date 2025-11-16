/**
 * Cover loading service with lazy loading using IntersectionObserver
 * Handles progressive cover image loading for audiobook results
 */

import { api } from '../core/api.js';

/**
 * CoverLoader service for lazy-loading cover images
 */
export class CoverLoader {
  constructor() {
    this.observer = null;
    this.rowStateStore = new Map();
  }

  /**
   * Initialize the IntersectionObserver
   * Should be called before observing any elements
   */
  init() {
    if (this.observer) return this.observer;

    this.observer = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          const container = entry.target;
          const mamId = container.dataset.mamId;
          const title = container.dataset.title;
          const author = container.dataset.author;
          const rowId = container.dataset.rowId;
          const rowState = rowId ? this.rowStateStore.get(rowId) : null;

          // Stop observing immediately to avoid duplicate fetches
          this.observer.unobserve(container);

          if (!mamId || !title) {
            container.innerHTML = '<div class="cover-placeholder">No info</div>';
            return;
          }

          // Fetch cover from backend with retry logic
          this.fetchCoverForItem(container, mamId, title, author, rowState);
        }
      });
    }, {
      rootMargin: '50px', // Start loading 50px before entering viewport
      threshold: 0.01
    });

    return this.observer;
  }

  /**
   * Observe a cover container element for lazy loading
   * @param {HTMLElement} element - Container element to observe
   */
  observe(element) {
    if (!this.observer) {
      this.init();
    }
    this.observer.observe(element);
  }

  /**
   * Store row state for later reference during cover fetching
   * @param {string} rowId - Unique row identifier
   * @param {Object} state - Row state data
   */
  setRowState(rowId, state) {
    this.rowStateStore.set(rowId, state);
  }

  /**
   * Get row state by ID
   * @param {string} rowId - Row identifier
   * @returns {Object|undefined} Row state or undefined
   */
  getRowState(rowId) {
    return this.rowStateStore.get(rowId);
  }

  /**
   * Clear all row state data
   */
  clearRowState() {
    this.rowStateStore.clear();
  }

  /**
   * Fetch and display cover image for an item
   * @param {HTMLElement} container - Container element to render cover into
   * @param {string} mamId - MAM torrent ID
   * @param {string} title - Book title
   * @param {string} author - Author name
   * @param {Object} rowState - Optional row state to update with cover info
   */
  async fetchCoverForItem(container, mamId, title, author, rowState = null) {
    try {
      container.classList.remove('cover-loaded');

      const data = await api.fetchCover({
        mam_id: mamId,
        title: title,
        author: author || '',
        max_retries: '2'
      });

      if (data.cover_url) {
        if (rowState) {
          rowState.abs_cover_url = data.cover_url;
          rowState.abs_item_id = data.item_id || rowState.abs_item_id || '';
        }

        // Create and load the image
        const img = document.createElement('img');
        img.className = 'cover-image';
        img.alt = 'Cover';
        img.src = data.cover_url;

        img.onload = () => {
          img.classList.add('loaded');
          container.innerHTML = '';
          container.appendChild(img);
          container.classList.add('cover-loaded');
        };

        img.onerror = () => {
          container.innerHTML = '<div class="cover-placeholder">No cover</div>';
          container.classList.remove('cover-loaded');
        };
      } else {
        if (rowState) {
          rowState.abs_cover_url = '';
          rowState.abs_item_id = '';
        }
        // No cover available or error
        const errorMsg = data.error || 'No cover';
        container.innerHTML = `<div class="cover-placeholder">${errorMsg === 'No cover found' ? 'No cover' : 'Error'}</div>`;
        container.classList.remove('cover-loaded');
      }
    } catch (e) {
      console.error('Cover fetch exception:', e);
      container.innerHTML = '<div class="cover-placeholder">Error</div>';
      container.classList.remove('cover-loaded');
    }
  }

  /**
   * Create a cover container element ready for lazy loading
   * @param {Object} params - Container parameters
   * @param {string} params.mamId - MAM torrent ID
   * @param {string} params.title - Book title
   * @param {string} params.author - Author name
   * @param {string} params.rowId - Optional row ID for state tracking
   * @returns {HTMLElement} Cover container element
   */
  createCoverContainer({ mamId, title, author, rowId = '' }) {
    const container = document.createElement('div');
    container.className = 'cover-skeleton';
    container.dataset.mamId = mamId || '';
    container.dataset.title = title || '';
    container.dataset.author = author || '';
    if (rowId) {
      container.dataset.rowId = rowId;
    }
    return container;
  }

  /**
   * Destroy the observer and clean up resources
   */
  destroy() {
    if (this.observer) {
      this.observer.disconnect();
      this.observer = null;
    }
    this.rowStateStore.clear();
  }
}
