/**
 * LibraryIndicator component - Creates visual indicators for items in ABS library
 */

/**
 * Create a library indicator element
 * @param {boolean} inLibrary - Whether the item is in the library
 * @returns {HTMLElement|null} - The indicator element, or null if not in library
 */
export function createLibraryIndicator(inLibrary) {
  if (!inLibrary) {
    return null;
  }

  const indicator = document.createElement('div');
  indicator.className = 'in-library-indicator';
  indicator.setAttribute('title', 'Already in your library');
  indicator.setAttribute('aria-label', 'Already in your library');

  // Use a checkmark character
  indicator.textContent = '✓';

  return indicator;
}

/**
 * Add library indicator to a cover container
 * @param {HTMLElement} coverContainer - The cover container element
 * @param {boolean} inLibrary - Whether the item is in the library
 * @returns {HTMLElement|null} - The indicator element if added, null otherwise
 */
export function addLibraryIndicator(coverContainer, inLibrary) {
  if (!coverContainer || !inLibrary) {
    return null;
  }

  // Check if indicator already exists
  const existingIndicator = coverContainer.querySelector('.in-library-indicator');
  if (existingIndicator) {
    return existingIndicator;
  }

  const indicator = createLibraryIndicator(inLibrary);
  if (indicator) {
    coverContainer.appendChild(indicator);
    return indicator;
  }

  return null;
}
