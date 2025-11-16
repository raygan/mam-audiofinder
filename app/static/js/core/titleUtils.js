/**
 * Title and author normalization utilities
 * Mirrors Python utils.py normalization functions for consistent client/server behavior
 */

/**
 * Normalize book title for series search matching
 *
 * Rules:
 * - Convert to lowercase
 * - Remove leading articles (The, A, An)
 * - Remove subtitles (text after :, -, –, —)
 * - Remove special characters
 * - Normalize whitespace
 *
 * @param {string} title - Book title to normalize
 * @returns {string} Normalized title
 *
 * @example
 * normalizeTitle("The Stormlight Archive: The Way of Kings")
 * // returns "stormlight archive"
 */
export function normalizeTitle(title) {
  if (!title) return '';

  let normalized = title.toLowerCase().trim();

  // Remove leading articles
  normalized = normalized.replace(/^(the|a|an)\s+/i, '');

  // Remove subtitles (after colon or dash variants)
  normalized = normalized.replace(/[:\-–—].+$/, '');

  // Remove special characters, keep only alphanumeric and spaces
  normalized = normalized.replace(/[^\w\s]/g, '');

  // Normalize whitespace
  normalized = normalized.replace(/\s+/g, ' ').trim();

  return normalized;
}

/**
 * Normalize author name for matching
 *
 * Rules:
 * - Convert to lowercase
 * - Remove special characters except spaces
 * - Normalize whitespace
 *
 * @param {string} author - Author name to normalize
 * @returns {string} Normalized author name
 *
 * @example
 * normalizeAuthor("J.R.R. Tolkien")
 * // returns "jrr tolkien"
 */
export function normalizeAuthor(author) {
  if (!author) return '';

  let normalized = author.toLowerCase().trim();

  // Remove periods and special characters
  normalized = normalized.replace(/[^\w\s]/g, '');

  // Normalize whitespace
  normalized = normalized.replace(/\s+/g, ' ').trim();

  return normalized;
}

/**
 * Generate unique identifier for a card
 *
 * Priority:
 * 1. Use MAM ID if available (unique per torrent)
 * 2. Generate hash from normalized title + author
 *
 * @param {string} mamId - MAM torrent ID (optional)
 * @param {string} title - Book title (optional)
 * @param {string} author - Author name (optional)
 * @returns {string} Unique card GUID
 *
 * @example
 * generateCardGuid('123456')
 * // returns "mam-123456"
 *
 * generateCardGuid('', 'Project Hail Mary', 'Andy Weir')
 * // returns "card-abc123def"
 */
export function generateCardGuid(mamId = '', title = '', author = '') {
  if (mamId) {
    return `mam-${mamId}`;
  }

  // Generate hash from normalized title + author
  const normalized = `${normalizeTitle(title)}||${normalizeAuthor(author)}`;
  return `card-${simpleHash(normalized)}`;
}

/**
 * Generate simple hash for string (for cache keys, GUIDs, etc.)
 *
 * Uses basic string hashing algorithm, returns hex representation
 *
 * @param {string} text - Text to hash
 * @returns {string} Hash string (12 chars max)
 */
export function simpleHash(text) {
  let hashValue = 0;

  for (let i = 0; i < text.length; i++) {
    const char = text.charCodeAt(i);
    hashValue = ((hashValue << 5) - hashValue) + char;
    hashValue = hashValue & 0xFFFFFFFF; // Convert to 32-bit integer
  }

  // Return absolute value as hex string, limited to 12 chars
  return Math.abs(hashValue).toString(16).substring(0, 12);
}
