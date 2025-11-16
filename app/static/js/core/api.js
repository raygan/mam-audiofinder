/**
 * Centralized API client for MAM Audiobook Finder
 * All backend API calls go through this module
 */

/**
 * API client with methods for all backend endpoints
 */
export const api = {
  /**
   * Health check endpoint
   * @returns {Promise<{ok: boolean}>}
   */
  async health() {
    const r = await fetch('/health');
    return r.json();
  },

  /**
   * Get application configuration
   * @returns {Promise<Object>}
   */
  async getConfig() {
    const r = await fetch('/config');
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return r.json();
  },

  /**
   * Search MAM for audiobooks
   * @param {Object} payload - Search parameters
   * @param {Object} payload.tor - Torrent search criteria
   * @param {string} payload.tor.text - Search query
   * @param {string} payload.tor.sortType - Sort type
   * @param {number} payload.perpage - Results per page
   * @returns {Promise<{results: Array}>}
   */
  async search(payload) {
    const resp = await fetch('/search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    return resp.json();
  },

  /**
   * Add torrent to qBittorrent
   * @param {Object} params - Torrent parameters
   * @returns {Promise<Object>}
   */
  async addTorrent(params) {
    const resp = await fetch('/add', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params)
    });
    if (!resp.ok) {
      let msg = `HTTP ${resp.status}`;
      try {
        const j = await resp.json();
        if (j?.detail) msg += ` — ${j.detail}`;
      } catch {}
      throw new Error(msg);
    }
    return resp.json();
  },

  /**
   * Get torrent history
   * @returns {Promise<{items: Array}>}
   */
  async getHistory() {
    const r = await fetch('/api/history', {
      cache: 'no-cache',
      headers: {
        'Cache-Control': 'no-cache, no-store, must-revalidate',
        'Pragma': 'no-cache'
      }
    });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const data = await r.json();
    console.log('[API] History response:', data.items?.length || 0, 'items');
    if (data.items?.length > 0) {
      console.log('[API] Sample item status:', {
        title: data.items[0].title,
        qb_status: data.items[0].qb_status,
        qb_status_color: data.items[0].qb_status_color,
        qb_hash: data.items[0].qb_hash
      });
    }
    return data;
  },

  /**
   * Delete history item
   * @param {number|string} id - History item ID
   * @returns {Promise<Object>}
   */
  async deleteHistoryItem(id) {
    const resp = await fetch(`/api/history/${encodeURIComponent(id)}`, {
      method: 'DELETE'
    });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    return resp.json();
  },

  /**
   * Manually trigger verification for a history item
   * @param {number|string} id - History item ID
   * @returns {Promise<{ok: boolean, verification: Object}>}
   */
  async verifyHistoryItem(id) {
    const resp = await fetch(`/api/history/${encodeURIComponent(id)}/verify`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' }
    });
    if (!resp.ok) {
      let msg = `HTTP ${resp.status}`;
      try {
        const j = await resp.json();
        if (j?.detail) msg += ` — ${j.detail}`;
      } catch {}
      throw new Error(msg);
    }
    return resp.json();
  },

  /**
   * Get completed torrents from qBittorrent
   * @returns {Promise<{items: Array}>}
   */
  async getCompletedTorrents() {
    const r = await fetch('/qb/torrents');
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return r.json();
  },

  /**
   * Get torrent file tree with multi-disc detection
   * @param {string} hash - Torrent hash
   * @returns {Promise<Object>}
   */
  async getTorrentTree(hash) {
    const r = await fetch(`/qb/torrent/${encodeURIComponent(hash)}/tree`);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return r.json();
  },

  /**
   * Import torrent to library
   * @param {Object} params - Import parameters
   * @param {string} params.author - Author name
   * @param {string} params.title - Book title
   * @param {string} params.hash - Torrent hash
   * @param {number} params.history_id - History item ID
   * @param {boolean} params.flatten - Whether to flatten multi-disc structure
   * @returns {Promise<Object>}
   */
  async importTorrent(params) {
    const r = await fetch('/import', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params)
    });
    if (!r.ok) {
      let msg = `HTTP ${r.status}`;
      try {
        const j = await r.json();
        if (j?.detail) msg += ` — ${j.detail}`;
      } catch {}
      throw new Error(msg);
    }
    return r.json();
  },

  /**
   * Get application logs
   * @param {Object} params - Log query parameters
   * @param {number} params.lines - Number of lines to retrieve
   * @param {string} params.level - Log level filter (INFO, WARNING, ERROR)
   * @returns {Promise<{ok: boolean, logs: Array<string>}>}
   */
  async getLogs(params) {
    const queryParams = new URLSearchParams({
      lines: params.lines.toString(),
      level: params.level || ''
    });
    const resp = await fetch(`/api/logs?${queryParams}`);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    return resp.json();
  },

  /**
   * Fetch cover image for an audiobook
   * @param {Object} params - Cover fetch parameters
   * @param {string} params.mam_id - MAM torrent ID
   * @param {string} params.title - Book title
   * @param {string} params.author - Author name
   * @param {string} params.max_retries - Maximum retry attempts
   * @returns {Promise<{cover_url?: string, item_id?: string, error?: string}>}
   */
  async fetchCover(params) {
    const queryParams = new URLSearchParams({
      mam_id: params.mam_id,
      title: params.title || '',
      author: params.author || '',
      max_retries: params.max_retries || '2'
    });
    const resp = await fetch(`/api/covers/fetch?${queryParams}`);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    return resp.json();
  },

  /**
   * Get showcase audiobooks (grouped by title)
   * @param {Object} params - Showcase query parameters
   * @param {string} params.query - Search query
   * @param {number} params.limit - Result limit
   * @returns {Promise<{groups: Array, total_groups: number, total_results: number}>}
   */
  async getShowcase(params) {
    const queryParams = new URLSearchParams({
      query: params.query || '',
      limit: params.limit.toString()
    });
    const resp = await fetch(`/api/showcase?${queryParams}`);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    return resp.json();
  }
};
