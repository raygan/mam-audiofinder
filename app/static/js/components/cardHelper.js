/**
 * Card Helper - Reusable component for creating book cards
 * Used in showcase, search, and history views
 */

import { addLibraryIndicator } from './libraryIndicator.js';

/**
 * Create a book card element with consistent styling and behavior
 *
 * @param {Object} config - Card configuration
 * @param {string} config.title - Book title
 * @param {string} config.author - Author name
 * @param {string} config.coverUrl - Cover image URL (optional, can be loaded later)
 * @param {string} config.mamId - MAM torrent ID
 * @param {Array<string>} config.formats - Available formats (e.g., ['MP3', 'M4B'])
 * @param {number} config.versionsCount - Number of versions available
 * @param {boolean} config.inLibrary - Whether item is in ABS library
 * @param {string} config.description - Book description (optional)
 * @param {Function} config.onClick - Click handler for the card
 * @param {string} config.cardClass - CSS class for the card (default: 'showcase-card')
 * @param {boolean} config.showDescription - Whether to show description (default: true)
 *
 * @returns {HTMLDivElement} The created card element
 */
export function createBookCard(config) {
  const {
    title = 'Unknown Title',
    author = 'Unknown Author',
    coverUrl = null,
    mamId = '',
    formats = [],
    versionsCount = 1,
    inLibrary = false,
    description = '',
    onClick = null,
    cardClass = 'showcase-card',
    showDescription = true,
  } = config;

  // Create card container
  const card = document.createElement('div');
  card.className = cardClass;
  card.dataset.mamId = mamId;
  card.dataset.title = title;
  card.dataset.author = author;

  // Create cover container (placeholder or actual image)
  const coverContainer = createCoverContainer(coverUrl, inLibrary);

  // Create versions badge (if multiple versions)
  const versionsBadge = createVersionsBadge(versionsCount);

  // Create title element
  const titleEl = document.createElement('div');
  titleEl.className = 'showcase-title';
  titleEl.textContent = title;

  // Create author element
  const authorEl = document.createElement('div');
  authorEl.className = 'showcase-author';
  authorEl.textContent = author;

  // Create formats display
  const formatsDiv = createFormatsDisplay(formats);

  // Create description element (if provided and enabled)
  let descriptionEl = null;
  if (showDescription && description) {
    descriptionEl = createExpandableDescription(description);
  }

  // Assemble card
  card.appendChild(versionsBadge);
  card.appendChild(coverContainer);
  card.appendChild(titleEl);
  card.appendChild(authorEl);
  card.appendChild(formatsDiv);
  if (descriptionEl) {
    card.appendChild(descriptionEl);
  }

  // Add click handler if provided
  if (onClick) {
    card.style.cursor = 'pointer';
    card.addEventListener('click', (e) => {
      // Don't trigger card click if clicking on description toggle
      if (e.target.classList.contains('description-toggle')) {
        return;
      }
      onClick(e);
    });
  }

  return card;
}

/**
 * Create cover container element
 * @private
 */
function createCoverContainer(coverUrl, inLibrary) {
  let container;

  if (coverUrl) {
    // Create actual image
    container = document.createElement('div');
    container.style.position = 'relative';

    const img = document.createElement('img');
    img.className = 'showcase-cover';
    img.src = coverUrl;
    img.alt = 'Cover';
    img.loading = 'lazy';

    container.appendChild(img);
  } else {
    // Create skeleton placeholder
    container = document.createElement('div');
    container.className = 'showcase-cover-skeleton';
  }

  // Add library indicator if item is in library
  if (inLibrary) {
    addLibraryIndicator(container, true);
  }

  return container;
}

/**
 * Create versions badge element
 * @private
 */
function createVersionsBadge(versionsCount) {
  const badge = document.createElement('div');
  badge.className = 'showcase-versions-badge';
  badge.textContent = `${versionsCount} version${versionsCount > 1 ? 's' : ''}`;
  return badge;
}

/**
 * Create formats display element
 * @private
 */
function createFormatsDisplay(formats) {
  const formatsDiv = document.createElement('div');
  formatsDiv.className = 'showcase-formats';

  formats.forEach(format => {
    const badge = document.createElement('span');
    badge.className = 'showcase-format-badge';
    badge.textContent = format;
    formatsDiv.appendChild(badge);
  });

  return formatsDiv;
}

/**
 * Create expandable description element
 * @private
 */
function createExpandableDescription(description) {
  const container = document.createElement('div');
  container.className = 'showcase-description-container';

  // Description text
  const descText = document.createElement('div');
  descText.className = 'showcase-description collapsed';
  descText.textContent = description;

  // Toggle button (only show if description is long enough)
  const shouldShowToggle = description.length > 200;
  let toggleBtn = null;

  if (shouldShowToggle) {
    toggleBtn = document.createElement('button');
    toggleBtn.className = 'description-toggle';
    toggleBtn.textContent = 'Show more';

    toggleBtn.addEventListener('click', (e) => {
      e.stopPropagation(); // Don't trigger card click
      const isCollapsed = descText.classList.contains('collapsed');

      if (isCollapsed) {
        descText.classList.remove('collapsed');
        toggleBtn.textContent = 'Show less';
      } else {
        descText.classList.add('collapsed');
        toggleBtn.textContent = 'Show more';
      }
    });
  } else {
    // Short description, don't collapse
    descText.classList.remove('collapsed');
  }

  // Source attribution
  const sourceAttr = document.createElement('div');
  sourceAttr.className = 'description-source';
  sourceAttr.textContent = 'via Audiobookshelf';

  // Assemble
  container.appendChild(descText);
  if (toggleBtn) {
    container.appendChild(toggleBtn);
  }
  container.appendChild(sourceAttr);

  return container;
}

/**
 * Update a card's cover image
 * Useful for progressive loading where cover is fetched after card creation
 *
 * @param {HTMLElement} card - The card element
 * @param {string} coverUrl - The cover URL to set
 */
export function updateCardCover(card, coverUrl) {
  if (!card || !coverUrl) return;

  const skeleton = card.querySelector('.showcase-cover-skeleton');
  if (!skeleton) return;

  // Preserve library indicator if it exists
  const libraryIndicator = skeleton.querySelector('.in-library-indicator');

  // Create new image
  const img = document.createElement('img');
  img.className = 'showcase-cover';
  img.src = coverUrl;
  img.alt = card.dataset.title || 'Cover';
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

    skeleton.replaceWith(wrapper);
  };

  img.onerror = () => {
    // Show placeholder on error
    const placeholder = document.createElement('div');
    placeholder.className = 'showcase-cover-placeholder';
    placeholder.textContent = 'No Cover';
    skeleton.replaceWith(placeholder);
  };
}

/**
 * Update a card's description
 * Useful when description is fetched after card creation
 *
 * @param {HTMLElement} card - The card element
 * @param {string} description - The description text
 */
export function updateCardDescription(card, description) {
  if (!card || !description) return;

  // Check if description already exists
  let descContainer = card.querySelector('.showcase-description-container');
  if (descContainer) {
    // Update existing description
    const descText = descContainer.querySelector('.showcase-description');
    if (descText) {
      descText.textContent = description;
    }
  } else {
    // Create new description and insert before formats or at end
    descContainer = createExpandableDescription(description);
    const formatsDiv = card.querySelector('.showcase-formats');
    if (formatsDiv && formatsDiv.nextSibling) {
      card.insertBefore(descContainer, formatsDiv.nextSibling);
    } else {
      card.appendChild(descContainer);
    }
  }
}
