/**
 * Series Search Button Component
 * Adds a "Find Series" button to book cards for Hardcover series discovery
 */

/**
 * Add series search button to a card element
 *
 * @param {HTMLElement} cardElement - The card DOM element
 * @param {string} viewName - Name of the view ('search', 'history', 'showcase')
 * @returns {HTMLElement} The created button element
 */
export function addSeriesSearchButton(cardElement, viewName = 'search') {
  if (!cardElement) return null;

  // Check if button already exists
  if (cardElement.querySelector('.series-search-btn')) {
    return cardElement.querySelector('.series-search-btn');
  }

  const button = document.createElement('button');
  button.className = 'series-search-btn';
  button.innerHTML = '🔍 Series';
  button.title = 'Find this book in a series';
  button.setAttribute('aria-label', 'Search for series');

  // Extract card data
  const cardData = {
    cardGuid: cardElement.dataset.cardGuid,
    mamId: cardElement.dataset.mamId || '',
    title: cardElement.dataset.title || '',
    author: cardElement.dataset.author || '',
    normalizedTitle: cardElement.dataset.normalizedTitle || '',
    normalizedAuthor: cardElement.dataset.normalizedAuthor || '',
    originView: viewName
  };

  // Add click handler
  button.addEventListener('click', (e) => {
    e.stopPropagation(); // Don't trigger card click
    e.preventDefault();

    // Dispatch series search event
    dispatchSeriesSearch(cardData);

    // Visual feedback
    button.classList.add('searching');
    button.innerHTML = '⏳ Searching...';
    button.disabled = true;
  });

  return button;
}

/**
 * Dispatch series search event
 *
 * @param {Object} cardData - Card metadata
 * @param {string} cardData.cardGuid - Unique card identifier
 * @param {string} cardData.mamId - MAM torrent ID
 * @param {string} cardData.title - Book title
 * @param {string} cardData.author - Author name
 * @param {string} cardData.normalizedTitle - Normalized title
 * @param {string} cardData.normalizedAuthor - Normalized author
 * @param {string} cardData.originView - Originating view name
 */
export function dispatchSeriesSearch(cardData) {
  const event = new CustomEvent('series-search', {
    detail: cardData,
    bubbles: true,
    cancelable: true
  });

  document.dispatchEvent(event);
}

/**
 * Reset series search button to default state
 *
 * @param {HTMLElement} button - The button element to reset
 */
export function resetSeriesSearchButton(button) {
  if (!button) return;

  button.classList.remove('searching', 'error', 'success');
  button.innerHTML = '🔍 Series';
  button.disabled = false;
}

/**
 * Set series search button to error state
 *
 * @param {HTMLElement} button - The button element
 * @param {string} message - Error message (optional)
 */
export function setSeriesSearchButtonError(button, message = 'Error') {
  if (!button) return;

  button.classList.remove('searching', 'success');
  button.classList.add('error');
  button.innerHTML = '⚠️ ' + message;
  button.disabled = false;

  // Auto-reset after 3 seconds
  setTimeout(() => resetSeriesSearchButton(button), 3000);
}

/**
 * Set series search button to success state
 *
 * @param {HTMLElement} button - The button element
 * @param {number} resultCount - Number of series found
 */
export function setSeriesSearchButtonSuccess(button, resultCount = 0) {
  if (!button) return;

  button.classList.remove('searching', 'error');
  button.classList.add('success');
  button.innerHTML = `✓ ${resultCount} series`;
  button.disabled = false;

  // Auto-reset after 2 seconds
  setTimeout(() => resetSeriesSearchButton(button), 2000);
}
