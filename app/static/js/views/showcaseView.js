/**
 * ShowcaseView module - Handles audiobook showcase grid and detail views
 */

import { api } from '../core/api.js';
import { escapeHtml, formatSize } from '../core/utils.js';
import { addLibraryIndicator } from '../components/libraryIndicator.js';

/**
 * ShowcaseView handles the showcase grid and detail display
 */
export class ShowcaseView {
  constructor(elements, router) {
    this.elements = elements;
    this.router = router;
    this.currentGroups = []; // Store loaded groups for detail view restoration
    this.currentDetailGroup = null;
    this.bindEvents();
  }

  /**
   * Bind event listeners
   */
  bindEvents() {
    // Search button
    this.elements.searchBtn?.addEventListener('click', async () => {
      const searchInput = this.elements.searchInput;
      await this.load(searchInput?.value || '');
    });

    // Search on Enter key
    this.elements.searchInput?.addEventListener('keypress', async (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        await this.load(e.target.value || '');
      }
    });

    // Limit selector
    this.elements.limitSelect?.addEventListener('change', async () => {
      await this.load();
    });
  }

  /**
   * Show empty state message when no search has been performed
   */
  showEmptyState() {
    const showcaseStatus = this.elements.status;
    const showcaseGrid = this.elements.grid;
    const showcaseDetail = this.elements.detail;

    if (!showcaseGrid || !showcaseStatus) return;

    showcaseStatus.textContent = 'Enter a search query to find audiobooks';
    showcaseGrid.innerHTML = '';
    if (showcaseDetail) showcaseDetail.style.display = 'none';
  }

  /**
   * Load and display showcase audiobooks
   * @param {string} query - Optional search query
   */
  async load(query = '') {
    const showcaseStatus = this.elements.status;
    const showcaseGrid = this.elements.grid;
    const showcaseDetail = this.elements.detail;

    if (!showcaseGrid || !showcaseStatus) return;

    try {
      // Get search query from input if not provided
      const searchQuery = query || this.elements.searchInput?.value?.trim() || '';
      const limit = parseInt(this.elements.limitSelect?.value || '100', 10);

      // Don't search if query is empty - show empty state instead
      if (!searchQuery) {
        this.showEmptyState();
        return;
      }

      showcaseStatus.textContent = 'Loading audiobooks...';
      showcaseGrid.innerHTML = '';
      showcaseDetail.style.display = 'none';

      const data = await api.getShowcase({
        query: searchQuery,
        limit: limit
      });

      if (!data.groups || data.groups.length === 0) {
        showcaseStatus.textContent = searchQuery
          ? `No audiobooks found matching "${searchQuery}".`
          : 'No audiobooks found. Try a different search.';
        return;
      }

      showcaseStatus.textContent = `Showing ${data.total_groups} titles (${data.total_results} versions)`;

      // Store groups for detail view restoration
      this.currentGroups = data.groups;

      this.renderGrid(data.groups);

      // Update URL with search parameters (if router is available)
      if (this.router) {
        this.router.updateURL({
          q: searchQuery,
          limit: limit.toString()
        }, true);
      }

    } catch (error) {
      console.error('Error loading showcase:', error);
      showcaseStatus.textContent = `Error loading showcase: ${error.message}`;
    }
  }

  /**
   * Render the showcase grid
   * @param {Array} groups - Grouped audiobook data
   */
  renderGrid(groups) {
    const showcaseGrid = this.elements.grid;
    if (!showcaseGrid) return;

    showcaseGrid.innerHTML = '';

    groups.forEach(group => {
      const card = this.createShowcaseCard(group);
      showcaseGrid.appendChild(card);
    });
  }

  /**
   * Create a showcase card element
   * @param {Object} group - Audiobook group data
   * @returns {HTMLDivElement}
   */
  createShowcaseCard(group) {
    const card = document.createElement('div');
    card.className = 'showcase-card';
    card.dataset.mamId = group.mam_id || '';
    card.dataset.title = group.display_title || '';
    card.dataset.author = group.author || '';

    // Create cover skeleton (will be replaced by actual cover)
    const coverSkeleton = document.createElement('div');
    coverSkeleton.className = 'showcase-cover-skeleton';

    // Add library indicator if group is in ABS library
    if (group.in_abs_library) {
      addLibraryIndicator(coverSkeleton, true);
    }

    // Create versions badge
    const versionsBadge = document.createElement('div');
    versionsBadge.className = 'showcase-versions-badge';
    versionsBadge.textContent = `${group.total_versions} version${group.total_versions > 1 ? 's' : ''}`;

    // Create title
    const title = document.createElement('div');
    title.className = 'showcase-title';
    title.textContent = group.display_title || 'Unknown Title';

    // Create author
    const author = document.createElement('div');
    author.className = 'showcase-author';
    author.textContent = group.author || 'Unknown Author';

    // Create formats
    const formatsDiv = document.createElement('div');
    formatsDiv.className = 'showcase-formats';
    (group.formats || []).forEach(format => {
      const badge = document.createElement('span');
      badge.className = 'showcase-format-badge';
      badge.textContent = format;
      formatsDiv.appendChild(badge);
    });

    // Assemble card
    card.appendChild(versionsBadge);
    card.appendChild(coverSkeleton);
    card.appendChild(title);
    card.appendChild(author);
    card.appendChild(formatsDiv);

    // Click handler to show detail view
    card.addEventListener('click', () => {
      this.showDetail(group);
    });

    // Lazy load cover
    if (group.mam_id && group.display_title) {
      this.loadShowcaseCover(coverSkeleton, group.mam_id, group.display_title, group.author);
    } else {
      const placeholder = document.createElement('div');
      placeholder.className = 'showcase-cover-placeholder';
      placeholder.textContent = 'No Cover';
      coverSkeleton.replaceWith(placeholder);
    }

    return card;
  }

  /**
   * Load cover for showcase card with retry, backoff, and jitter
   * @param {HTMLElement} skeletonEl - Skeleton element to replace
   * @param {string} mamId - MAM torrent ID
   * @param {string} title - Book title
   * @param {string} author - Author name
   */
  async loadShowcaseCover(skeletonEl, mamId, title, author) {
    // Add random initial jitter to spread out concurrent requests (0-500ms)
    const initialJitter = Math.random() * 500;
    await new Promise(resolve => setTimeout(resolve, initialJitter));

    const maxRetries = 3;
    let attempt = 0;

    while (attempt <= maxRetries) {
      try {
        // Preserve library indicator if it exists
        const libraryIndicator = skeletonEl.querySelector('.in-library-indicator');

        const data = await api.fetchCover({
          mam_id: mamId,
          title: title || '',
          author: author || '',
          max_retries: '3'
        });

        if (data.cover_url) {
          const img = document.createElement('img');
          img.className = 'showcase-cover';
          img.src = data.cover_url;
          img.alt = title || 'Cover';
          img.loading = 'lazy';

          img.onload = () => {
            // Create wrapper to maintain relative positioning for indicator
            const wrapper = document.createElement('div');
            wrapper.style.position = 'relative';
            wrapper.appendChild(img);

            // Re-add library indicator if it existed
            if (libraryIndicator) {
              wrapper.appendChild(libraryIndicator);
            }

            skeletonEl.replaceWith(wrapper);
          };

          img.onerror = () => {
            const placeholder = document.createElement('div');
            placeholder.className = 'showcase-cover-placeholder';
            placeholder.textContent = '📚';

            // Re-add library indicator if it existed
            if (libraryIndicator) {
              placeholder.style.position = 'relative';
              placeholder.appendChild(libraryIndicator);
            }

            skeletonEl.replaceWith(placeholder);
          };

          // Success - exit retry loop
          return;
        } else {
          const placeholder = document.createElement('div');
          placeholder.className = 'showcase-cover-placeholder';
          placeholder.textContent = '📚';

          // Re-add library indicator if it existed
          if (libraryIndicator) {
            placeholder.style.position = 'relative';
            placeholder.appendChild(libraryIndicator);
          }

          skeletonEl.replaceWith(placeholder);
          return;
        }
      } catch (error) {
        attempt++;

        if (attempt > maxRetries) {
          // Final failure - show placeholder
          console.error(`Failed to load cover after ${maxRetries} retries:`, error);
          const libraryIndicator = skeletonEl.querySelector('.in-library-indicator');
          const placeholder = document.createElement('div');
          placeholder.className = 'showcase-cover-placeholder';
          placeholder.textContent = '📚';

          if (libraryIndicator) {
            placeholder.style.position = 'relative';
            placeholder.appendChild(libraryIndicator);
          }

          skeletonEl.replaceWith(placeholder);
          return;
        }

        // Exponential backoff with scaled jitter
        // Base delay: 2^attempt seconds, jitter: 0 to (base delay * 0.5)
        const baseDelay = Math.pow(2, attempt) * 1000;
        const jitter = Math.random() * (baseDelay * 0.5);
        const retryDelay = baseDelay + jitter;

        console.log(`Cover load failed (attempt ${attempt}), retrying in ${Math.round(retryDelay)}ms...`);
        await new Promise(resolve => setTimeout(resolve, retryDelay));
      }
    }
  }

  /**
   * Find and show detail view by normalized title from URL
   * @param {string} detailIdentifier - Normalized title from URL parameter
   */
  showDetailByIdentifier(detailIdentifier) {
    if (!this.currentGroups || this.currentGroups.length === 0) {
      console.warn('Cannot show detail: no groups loaded');
      return;
    }

    // Find group by normalized title or display title slug
    const group = this.currentGroups.find(g => {
      const normalizedMatch = g.normalized_title === detailIdentifier;
      const slugMatch = g.display_title?.toLowerCase().replace(/\s+/g, '-') === detailIdentifier;
      return normalizedMatch || slugMatch;
    });

    if (group) {
      this.showDetail(group, false); // Don't update history - we're restoring from URL
    } else {
      console.warn(`Cannot find group with identifier: ${detailIdentifier}`);
    }
  }

  /**
   * Show detail view for a group
   * @param {Object} group - Audiobook group data
   * @param {boolean} updateHistory - Whether to push state to browser history (default true)
   */
  showDetail(group, updateHistory = true) {
    const showcaseDetail = this.elements.detail;
    const showcaseGrid = this.elements.grid;
    if (!showcaseDetail) return;

    // Store group for later reference (e.g., back button)
    this.currentDetailGroup = group;

    // Update URL with detail parameter
    if (updateHistory && this.router) {
      const currentState = this.router.getStateFromURL();
      const newState = {
        ...currentState,
        detail: group.normalized_title || group.display_title?.toLowerCase().replace(/\s+/g, '-') || 'unknown'
      };
      this.router.updateURL(newState, false); // Push new state
    }

    // Hide grid, show detail
    if (showcaseGrid) showcaseGrid.style.display = 'none';
    showcaseDetail.style.display = '';

    // Build detail view HTML
    let html = '<button class="showcase-detail-close" id="showcaseDetailCloseBtn">✕ Close</button>';

    html += '<div class="showcase-detail-header">';

    // Cover
    if (group.versions && group.versions[0]) {
      html += '<div>';
      html += `<div class="showcase-cover-skeleton" id="detailCoverSkeleton"></div>`;
      html += '</div>';
    }

    // Info
    html += '<div class="showcase-detail-info">';
    html += `<h2 class="showcase-detail-title">${escapeHtml(group.display_title || 'Unknown Title')}</h2>`;
    if (group.author) {
      html += `<div class="showcase-detail-author">by ${escapeHtml(group.author)}</div>`;
    }
    if (group.narrator) {
      html += `<div class="showcase-detail-narrator">Narrated by ${escapeHtml(group.narrator)}</div>`;
    }
    html += '<div class="showcase-formats">';
    (group.formats || []).forEach(format => {
      html += `<span class="showcase-format-badge">${escapeHtml(format)}</span>`;
    });
    html += '</div>';
    html += '</div>'; // Close info
    html += '</div>'; // Close header

    // Versions table
    html += '<h3>Available Versions (' + group.total_versions + ')</h3>';
    html += '<table class="showcase-versions-table">';
    html += '<thead><tr>';
    html += '<th>Title</th>';
    html += '<th>Format</th>';
    html += '<th class="right">Size</th>';
    html += '<th class="right">Seeders</th>';
    html += '<th>Added</th>';
    html += '<th class="center">Link</th>';
    html += '<th>Add</th>';
    html += '</tr></thead>';
    html += '<tbody>';

    (group.versions || []).forEach((version, idx) => {
      const detailsURL = version.id ? `https://www.myanonamouse.net/t/${encodeURIComponent(version.id)}` : '';
      html += '<tr>';
      html += `<td>${escapeHtml(version.title || 'Unknown')}</td>`;
      html += `<td>${escapeHtml(version.format || '')}</td>`;
      html += `<td class="right">${formatSize(version.size)}</td>`;
      html += `<td class="right">${version.seeders || 0}</td>`;
      html += `<td>${version.added || ''}</td>`;
      html += `<td class="center">`;
      if (detailsURL) {
        html += `<a href="${detailsURL}" target="_blank" rel="noopener noreferrer" title="Open on MAM">🔗</a>`;
      }
      html += `</td>`;
      html += `<td>`;
      html += `<button class="showcase-add-btn" data-version-idx="${idx}">Add</button>`;
      html += `</td>`;
      html += '</tr>';
    });

    html += '</tbody></table>';

    showcaseDetail.innerHTML = html;

    // Add event listener for close button
    const closeBtn = document.getElementById('showcaseDetailCloseBtn');
    if (closeBtn) {
      closeBtn.addEventListener('click', () => this.closeDetail());
    }

    // Add event listeners for all Add buttons
    const addButtons = showcaseDetail.querySelectorAll('.showcase-add-btn');
    addButtons.forEach(btn => {
      const versionIdx = parseInt(btn.dataset.versionIdx, 10);
      const version = group.versions[versionIdx];
      if (!version) return;

      btn.disabled = !(version.dl || version.id);
      btn.addEventListener('click', async () => {
        await this.addVersion(btn, version, group);
      });
    });

    // Load cover for first version
    if (group.mam_id && group.display_title) {
      setTimeout(() => {
        const skeleton = document.getElementById('detailCoverSkeleton');
        if (skeleton) {
          this.loadDetailCover(skeleton, group.mam_id, group.display_title, group.author);
        }
      }, 100);
    }

    // Scroll to detail
    showcaseDetail.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  /**
   * Close detail view and show grid
   * @param {boolean} updateHistory - Whether to update browser history (default true)
   */
  closeDetail(updateHistory = true) {
    const showcaseDetail = this.elements.detail;
    const showcaseGrid = this.elements.grid;

    if (showcaseDetail) showcaseDetail.style.display = 'none';
    if (showcaseGrid) showcaseGrid.style.display = '';

    // Clear stored group
    this.currentDetailGroup = null;

    // Update URL to remove detail parameter
    if (updateHistory && this.router) {
      // Use history.back() to go back to previous state
      window.history.back();
    }
  }

  /**
   * Add a version to qBittorrent
   * @param {HTMLButtonElement} btn - Add button
   * @param {Object} version - Version data
   * @param {Object} group - Group data
   */
  async addVersion(btn, version, group) {
    btn.disabled = true;
    btn.textContent = 'Adding…';
    try {
      await api.addTorrent({
        id: String(version.id || ''),
        title: version.title || '',
        dl: version.dl || '',
        author: group.author || '',
        narrator: group.narrator || '',
        abs_cover_url: '',
        abs_item_id: ''
      });

      btn.textContent = 'Added';

      // Notify that history should be reloaded
      window.dispatchEvent(new CustomEvent('torrentAdded'));

    } catch (e) {
      console.error(e);
      btn.textContent = 'Error';
      btn.disabled = false;
    }
  }

  /**
   * Load cover for detail view with retry, backoff, and jitter
   * @param {HTMLElement} skeletonEl - Skeleton element
   * @param {string} mamId - MAM ID
   * @param {string} title - Title
   * @param {string} author - Author
   */
  async loadDetailCover(skeletonEl, mamId, title, author) {
    const maxRetries = 3;
    let attempt = 0;

    while (attempt <= maxRetries) {
      try {
        const data = await api.fetchCover({
          mam_id: mamId,
          title: title || '',
          author: author || '',
          max_retries: '3'
        });

        if (data.cover_url) {
          const img = document.createElement('img');
          img.className = 'showcase-detail-cover';
          img.src = data.cover_url;
          img.alt = title || 'Cover';

          img.onload = () => {
            skeletonEl.replaceWith(img);
          };

          img.onerror = () => {
            skeletonEl.style.display = 'none';
          };

          return; // Success
        } else {
          skeletonEl.style.display = 'none';
          return;
        }
      } catch (error) {
        attempt++;

        if (attempt > maxRetries) {
          console.error(`Failed to load detail cover after ${maxRetries} retries:`, error);
          skeletonEl.style.display = 'none';
          return;
        }

        // Exponential backoff with scaled jitter
        const baseDelay = Math.pow(2, attempt) * 1000;
        const jitter = Math.random() * (baseDelay * 0.5);
        const retryDelay = baseDelay + jitter;

        console.log(`Detail cover load failed (attempt ${attempt}), retrying in ${Math.round(retryDelay)}ms...`);
        await new Promise(resolve => setTimeout(resolve, retryDelay));
      }
    }
  }
}
