/**
 * ImportForm component - Handles torrent import workflow
 */

import { api } from '../core/api.js';
import { escapeHtml, formatSize } from '../core/utils.js';

/**
 * ImportForm component for importing torrents to library
 */
export class ImportForm {
  constructor(historyItem, expanderRow, historyTable) {
    this.historyItem = historyItem;
    this.expanderRow = expanderRow;
    this.historyTable = historyTable;
    this.treeData = null;
    this.elements = {};
  }

  /**
   * Render the import form
   */
  async render() {
    // Fetch config to get import mode
    let buttonText = 'Copy to Library';
    try {
      const cfg = await api.getConfig();
      if (cfg.import_mode === 'link') {
        buttonText = 'Link to Library';
      } else if (cfg.import_mode === 'move') {
        buttonText = 'Move to Library';
      }
    } catch (e) {
      console.error('Failed to fetch config', e);
    }

    const h = this.historyItem;
    const expTd = this.expanderRow.querySelector('td');

    expTd.innerHTML = `
      <div class="import-form">
        <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center;">
          <span>Import:</span>
          <span>/</span>
          <input type="text" class="imp-author" placeholder="Author" value="${escapeHtml(h.author || '')}" style="min-width:220px;">
          <span>/</span>
          <input type="text" class="imp-title" placeholder="Title" value="${escapeHtml(h.title || '')}" style="min-width:280px;">
          <span>/</span>
          <select class="imp-torrent" style="min-width:320px;">
            <option disabled selected>Loading torrents…</option>
          </select>
          <button class="imp-go">${buttonText}</button>
        </div>
        <div style="display:flex;gap:12px;margin-top:8px;align-items:center;flex-wrap:wrap;">
          <label style="display:flex;align-items:center;gap:4px;cursor:pointer;">
            <input type="checkbox" class="imp-flatten" style="cursor:pointer;">
            <span>Flatten multi-disc structure</span>
          </label>
          <button class="imp-view-files" style="font-size:0.9em;">📁 View Files</button>
          <span class="imp-detection-hint" style="font-size:0.9em;color:#666;"></span>
        </div>
        <div class="imp-tree-view" style="display:none;"></div>
        <div class="imp-status" style="margin-top:6px;color:#666;"></div>
      </div>
    `;

    // Store element references
    this.elements = {
      authorInput: expTd.querySelector('.imp-author'),
      titleInput: expTd.querySelector('.imp-title'),
      torrentSelect: expTd.querySelector('.imp-torrent'),
      goBtn: expTd.querySelector('.imp-go'),
      statusEl: expTd.querySelector('.imp-status'),
      flattenCheckbox: expTd.querySelector('.imp-flatten'),
      viewFilesBtn: expTd.querySelector('.imp-view-files'),
      treeView: expTd.querySelector('.imp-tree-view'),
      detectionHint: expTd.querySelector('.imp-detection-hint')
    };

    await this.loadTorrents();
    this.bindEvents();
  }

  /**
   * Load available torrents from qBittorrent
   */
  async loadTorrents() {
    let torrents = [];
    let matchedTorrent = null;

    try {
      const data = await api.getCompletedTorrents();
      torrents = data.items || [];
      this.elements.torrentSelect.innerHTML = '';

      const h = this.historyItem;
      const historyHash = h.qb_hash;
      const historyMamId = String(h.mam_id || '').trim();

      if (torrents.length) {
        // Try to match by hash first
        if (historyHash) {
          matchedTorrent = torrents.find(t => t.hash === historyHash);
        }

        // Fallback: match by mam_id
        if (!matchedTorrent && historyMamId) {
          matchedTorrent = torrents.find(t => String(t.mam_id || '').trim() === historyMamId);
        }

        // Populate dropdown with all torrents
        torrents.forEach(t => {
          const opt = document.createElement('option');
          opt.value = t.hash;
          opt.dataset.mamId = t.mam_id || '';
          opt.dataset.contentPath = t.content_path || t.save_path || '';

          // Mark matched torrent
          const isMatched = matchedTorrent && t.hash === matchedTorrent.hash;
          const matchSuffix = isMatched ? ' (MATCHED)' : '';
          opt.textContent = `${t.name}  —  ${t.single_file ? 'single-file' : (t.root || t.name)}${matchSuffix}`;

          if (isMatched) {
            opt.selected = true;
          }

          this.elements.torrentSelect.appendChild(opt);
        });

        // Show initial status message
        if (matchedTorrent) {
          this.elements.statusEl.innerHTML = '<span style="color: #27ae60;">✓ Torrent auto-selected based on match</span>';

          // Trigger auto-detection for the matched torrent
          this.detectMultiDisc(matchedTorrent.hash);
        } else if (historyHash || historyMamId) {
          this.elements.statusEl.innerHTML = '<span style="color: #f39c12;">⚠️ No matching torrent found - please select manually</span>';
        }
      } else {
        const opt = document.createElement('option');
        opt.disabled = true;
        opt.selected = true;
        opt.textContent = 'No completed torrents in category';
        this.elements.torrentSelect.appendChild(opt);
      }
    } catch (e) {
      console.error(e);
      this.elements.torrentSelect.innerHTML = '<option disabled selected>Failed to load torrents</option>';
    }
  }

  /**
   * Bind event listeners
   */
  bindEvents() {
    // Torrent selection change
    this.elements.torrentSelect.addEventListener('change', async () => {
      await this.handleTorrentChange();
    });

    // View files button
    this.elements.viewFilesBtn.addEventListener('click', () => {
      this.toggleTreeView();
    });

    // Flatten checkbox change
    this.elements.flattenCheckbox.addEventListener('change', () => {
      if (this.elements.treeView.style.display !== 'none' && this.treeData) {
        this.elements.treeView.innerHTML = this.renderTreeView(this.treeData, this.elements.flattenCheckbox.checked);
      }
    });

    // Import button
    this.elements.goBtn.addEventListener('click', async (ev) => {
      ev.preventDefault();
      await this.performImport();
    });
  }

  /**
   * Handle torrent selection change
   */
  async handleTorrentChange() {
    const selectedOption = this.elements.torrentSelect.options[this.elements.torrentSelect.selectedIndex];
    const selectedMamId = selectedOption?.dataset.mamId || '';
    const selectedContentPath = selectedOption?.dataset.contentPath || '';
    const historyMamId = String(this.historyItem.mam_id || '').trim();
    const hash = this.elements.torrentSelect.value;

    let warnings = [];

    // Check if selected torrent matches history item
    if (historyMamId && selectedMamId !== historyMamId) {
      const selectedName = selectedOption?.textContent?.split('—')[0].trim() || 'Unknown';
      warnings.push(`<span style="color: #f39c12;">⚠️ This torrent does not match the history item</span><br>
        <span style="font-size: 0.9em;">Selected: ${escapeHtml(selectedName)} | Expected: ${escapeHtml(this.historyItem.title || 'Unknown')}</span>`);
    }

    // Check if torrent path seems valid
    if (selectedContentPath && !selectedContentPath.includes('/media/')) {
      warnings.push(`<span style="color: #e74c3c;">❌ Torrent download dir does not match expected path - hardlink may fail</span>`);
    }

    if (warnings.length > 0) {
      this.elements.statusEl.innerHTML = warnings.join('<br>');
    } else if (historyMamId && selectedMamId === historyMamId) {
      this.elements.statusEl.innerHTML = '<span style="color: #27ae60;">✓ Torrent matches history item</span>';
    } else {
      this.elements.statusEl.textContent = '';
    }

    // Fetch tree data and run chapter detector
    if (hash && hash !== 'Loading torrents…') {
      await this.detectMultiDisc(hash);

      // Update tree view if it's already open
      if (this.elements.treeView.style.display !== 'none') {
        this.elements.treeView.innerHTML = this.renderTreeView(this.treeData, this.elements.flattenCheckbox.checked);
      }
    }
  }

  /**
   * Detect multi-disc structure and update UI
   * @param {string} hash - Torrent hash
   */
  async detectMultiDisc(hash) {
    try {
      this.treeData = await api.getTorrentTree(hash);

      if (this.treeData) {
        if (this.treeData.recommended_flatten) {
          this.elements.flattenCheckbox.checked = true;
          this.elements.detectionHint.innerHTML = `<span style="color:#27ae60;">✓ Multi-disc detected (${this.treeData.disc_count} discs) - flatten recommended</span>`;
        } else if (this.treeData.single_file) {
          this.elements.flattenCheckbox.checked = false;
          this.elements.flattenCheckbox.disabled = true;
          this.elements.detectionHint.innerHTML = '<span style="color:#999;">Single file - flatten not applicable</span>';
        } else {
          this.elements.flattenCheckbox.checked = false;
          this.elements.flattenCheckbox.disabled = false;
          this.elements.detectionHint.textContent = '';
        }
      }
    } catch (e) {
      console.error('Error detecting multi-disc:', e);
    }
  }

  /**
   * Toggle tree view visibility
   */
  toggleTreeView() {
    if (this.elements.treeView.style.display === 'none') {
      if (this.treeData) {
        this.elements.treeView.innerHTML = this.renderTreeView(this.treeData, this.elements.flattenCheckbox.checked);
        this.elements.treeView.style.display = 'block';
        this.elements.viewFilesBtn.textContent = '📁 Hide Files';
      } else {
        this.elements.treeView.innerHTML = '<div style="color:#f39c12;">Please select a torrent first</div>';
        this.elements.treeView.style.display = 'block';
        this.elements.viewFilesBtn.textContent = '📁 Hide Files';
      }
    } else {
      this.elements.treeView.style.display = 'none';
      this.elements.viewFilesBtn.textContent = '📁 View Files';
    }
  }

  /**
   * Render file tree view
   * @param {Object} data - Tree data from API
   * @param {boolean} showFlattened - Whether to show flattened preview
   * @returns {string} HTML string
   */
  renderTreeView(data, showFlattened) {
    if (!data || !data.files || data.files.length === 0) {
      return '<div style="color:#999;">No files found</div>';
    }

    const files = data.files;

    if (showFlattened && data.has_disc_structure) {
      // Show flattened preview
      let html = '<div style="margin-bottom:8px;color:#27ae60;font-weight:bold;">📁 Preview after flatten:</div>';

      // Build file list
      const fileList = [];
      for (const file of files) {
        if (file.path.toLowerCase().endsWith('.cue')) continue;
        fileList.push(file);
      }

      // Sort and number them
      html += '<div style="margin-left:16px;">';
      fileList.forEach((file, idx) => {
        const ext = file.path.substring(file.path.lastIndexOf('.'));
        const newName = `Part ${String(idx + 1).padStart(3, '0')}${ext}`;
        const sizeStr = formatSize(file.size);
        html += `<div>🎵 ${escapeHtml(newName)} <span style="color:#999;font-size:0.9em;">(was: ${escapeHtml(file.path)}) - ${sizeStr}</span></div>`;
      });
      html += '</div>';

      return html;
    } else {
      // Show original structure
      let html = '<div style="margin-bottom:8px;font-weight:bold;">📁 Original structure:</div>';

      // Build hierarchical view
      const tree = {};
      for (const file of files) {
        const parts = file.path.split('/');
        let current = tree;

        for (let i = 0; i < parts.length; i++) {
          const part = parts[i];
          if (i === parts.length - 1) {
            // File
            if (!current._files) current._files = [];
            current._files.push({ name: part, size: file.size });
          } else {
            // Directory
            if (!current[part]) current[part] = {};
            current = current[part];
          }
        }
      }

      // Render tree recursively
      const renderNode = (node, depth = 0) => {
        let result = '';

        // Render directories first
        for (const [key, value] of Object.entries(node)) {
          if (key === '_files') continue;
          result += `<div style="margin-left:${depth * 16}px;">📁 ${escapeHtml(key)}/</div>`;
          result += renderNode(value, depth + 1);
        }

        // Then files
        if (node._files) {
          for (const file of node._files) {
            const sizeStr = formatSize(file.size);
            result += `<div style="margin-left:${depth * 16}px;">🎵 ${escapeHtml(file.name)} <span style="color:#999;font-size:0.9em;">- ${sizeStr}</span></div>`;
          }
        }

        return result;
      };

      html += renderNode(tree);
      return html;
    }
  }

  /**
   * Perform the import operation
   */
  async performImport() {
    const author = this.elements.authorInput.value.trim();
    const title = this.elements.titleInput.value.trim();
    const hash = this.elements.torrentSelect.value;

    if (!author || !title || !hash) {
      this.elements.statusEl.textContent = 'Please fill Author, Title, and select a torrent.';
      return;
    }

    this.elements.goBtn.disabled = true;
    this.elements.statusEl.textContent = 'Importing…';

    try {
      const flatten = this.elements.flattenCheckbox.checked;
      const result = await api.importTorrent({
        author,
        title,
        hash,
        history_id: this.historyItem.id,
        flatten
      });

      // Build status message with statistics
      let statusMsg = `Done → ${result.dest} (${result.files_copied || '?'} files`;
      if (result.import_mode === 'link') {
        if (result.files_linked > 0) {
          statusMsg += `, ${result.files_linked} hardlinked`;
          if (result.files_copied > result.files_linked) {
            statusMsg += `, ${result.files_copied - result.files_linked} copied`;
          }
        } else {
          statusMsg += ', all copied (hardlink failed)';
        }
      } else if (result.import_mode === 'move') {
        statusMsg += ', moved';
      } else {
        statusMsg += ', copied';
      }
      statusMsg += ')';

      this.elements.statusEl.textContent = statusMsg;
      this.elements.goBtn.textContent = result.import_mode === 'link' ? 'Linked' : result.import_mode === 'move' ? 'Moved' : 'Imported';

      // Notify parent that import completed
      window.dispatchEvent(new CustomEvent('importCompleted', {
        detail: { historyId: this.historyItem.id }
      }));

    } catch (e) {
      console.error(e);
      this.elements.statusEl.textContent = `Failed: ${e.message}`;
      this.elements.goBtn.disabled = false;
    }
  }
}
