/**
 * Media Discovery Feed Sidebar
 */

(function () {
  'use strict';

  const TABS = [
    { id: 'all', label: 'All' },
    { id: 'movies', label: 'Movies' },
    { id: 'tv', label: 'TV Shows' },
    { id: 'anime', label: 'Anime' },
    { id: 'recommended', label: 'Recommended', requiresService: true },
  ];

  let currentType = 'all';
  let currentPage = 1;
  let mediaStatus = {};
  let isLoading = false;
  let hasLoadedInitialFeed = false;

  // -------------------------------------------------------------------------
  // Init
  // -------------------------------------------------------------------------

  async function initMediaFeed() {
    renderTabs();
    restoreSidebarState();
    setupLoadMore();
    setupToggle();

    const sidebarCollapsed = localStorage.getItem('mediaSidebarCollapsed') === 'true';
    if (sidebarCollapsed) return;

    try {
      const res = await fetch('/api/media/status/');
      mediaStatus = await res.json();
    } catch (e) {
      mediaStatus = {};
    }

    renderTabs();
    setTimeout(loadInitialFeed, 500);
  }

  async function loadInitialFeed() {
    if (hasLoadedInitialFeed) return;
    hasLoadedInitialFeed = true;
    await loadMediaFeed('all', 1, false);
  }

  // -------------------------------------------------------------------------
  // Tabs
  // -------------------------------------------------------------------------

  function renderTabs() {
    const container = document.getElementById('media-tabs');
    if (!container) return;

    const showRecommended = mediaStatus.radarr_available || mediaStatus.sonarr_available;
    container.innerHTML = '';

    TABS.forEach(tab => {
      if (tab.requiresService && !showRecommended) return;

      const btn = document.createElement('button');
      btn.dataset.tabId = tab.id;
      btn.textContent = tab.label;
      btn.className = [
        'px-3 py-2 text-xs font-medium whitespace-nowrap transition-colors border-b-2',
        tab.id === currentType
          ? 'border-primary text-primary'
          : 'border-transparent text-text-secondary hover:text-text-primary',
      ].join(' ');

      btn.addEventListener('click', () => {
        currentType = tab.id;
        currentPage = 1;
        // Update active styles
        container.querySelectorAll('button').forEach(b => {
          const active = b.dataset.tabId === currentType;
          b.className = [
            'px-3 py-2 text-xs font-medium whitespace-nowrap transition-colors border-b-2',
            active ? 'border-primary text-primary' : 'border-transparent text-text-secondary hover:text-text-primary',
          ].join(' ');
        });
        loadMediaFeed(currentType, 1, false);
      });

      container.appendChild(btn);
    });
  }

  // -------------------------------------------------------------------------
  // Load feed
  // -------------------------------------------------------------------------

  async function loadMediaFeed(type, page, append = false) {
    if (isLoading) return;
    isLoading = true;

    const feedList = document.getElementById('media-feed-list');
    const loadMoreBtn = document.getElementById('load-more-btn');

    if (!append) {
      // Show skeleton
      feedList.innerHTML = [1, 2, 3].map(() => `
        <div class="animate-pulse flex gap-2 p-2 rounded-lg bg-bg-card">
          <div class="w-16 h-24 bg-bg-secondary rounded shrink-0"></div>
          <div class="flex-1 space-y-2 py-1">
            <div class="h-3 bg-bg-secondary rounded w-3/4"></div>
            <div class="h-2 bg-bg-secondary rounded w-1/2"></div>
            <div class="h-2 bg-bg-secondary rounded w-full"></div>
            <div class="h-2 bg-bg-secondary rounded w-5/6"></div>
          </div>
        </div>
      `).join('');
    }

    try {
      const res = await fetch(`/api/media/feed/?type=${type}&page=${page}`);
      const data = await res.json();

      const showAddButton = mediaStatus.radarr_available || mediaStatus.sonarr_available;

      if (!append) {
        feedList.innerHTML = '';
      } else {
        // Remove skeleton if any
      }

      if (!data.items || data.items.length === 0) {
        if (!append) {
          feedList.innerHTML = '<p class="text-text-secondary text-xs text-center py-8">No items found.</p>';
        }
      } else {
        data.items.forEach(item => {
          const div = document.createElement('div');
          div.innerHTML = renderMediaCard(item, showAddButton);
          feedList.appendChild(div.firstElementChild);
        });
      }

      if (loadMoreBtn) {
        if (data.has_more) {
          loadMoreBtn.classList.remove('hidden');
          loadMoreBtn.dataset.nextPage = page + 1;
          loadMoreBtn.dataset.type = type;
        } else {
          loadMoreBtn.classList.add('hidden');
        }
      }
    } catch (e) {
      if (!append) {
        feedList.innerHTML = '<p class="text-danger text-xs text-center py-8">Failed to load feed.</p>';
      }
    }

    isLoading = false;
  }

  // -------------------------------------------------------------------------
  // Card renderer
  // -------------------------------------------------------------------------

  function renderMediaCard(item, showAddButton) {
    const poster = item.poster_url
      ? `<img src="${escHtml(item.poster_url)}" alt="" class="w-16 h-24 object-cover rounded shrink-0" loading="lazy">`
      : `<div class="w-16 h-24 rounded shrink-0 flex items-center justify-center text-2xl"
              style="background: hsl(${(item.title.charCodeAt(0) * 7) % 360},30%,25%)">🎬</div>`;

    const year = item.year ? `<span class="text-text-secondary">${item.year}</span>` : '';
    const rating = item.rating != null ? `<span>⭐ ${Number(item.rating).toFixed(1)}</span>` : '';
    const genres = (item.genres || []).slice(0, 3)
      .map(g => `<span class="px-1.5 py-0.5 bg-bg-secondary rounded text-xs text-text-secondary">${escHtml(g)}</span>`)
      .join('');
    const desc = item.description
      ? `<p class="text-xs text-text-secondary line-clamp-2 mt-1">${escHtml(item.description)}</p>`
      : '';

    let addBtn = '';
    if (showAddButton && !item.in_library) {
      const label = item.type === 'movie' ? '＋ Radarr' : '＋ Sonarr';
      const itemJson = escHtml(JSON.stringify(item));
      addBtn = `<button onclick="window._mediaAddToLibrary(${itemJson})" 
                        class="mt-1 px-2 py-1 text-xs bg-primary text-white rounded hover:bg-primary-hover transition-colors">
                  ${label}
                </button>`;
    } else if (item.in_library) {
      addBtn = `<span class="mt-1 text-xs text-success">✓ In Library</span>`;
    }

    return `
      <div class="flex gap-2 p-2 rounded-lg bg-bg-card hover:bg-bg-secondary transition-colors cursor-default">
        ${poster}
        <div class="flex-1 min-w-0">
          <div class="font-medium text-sm truncate">${escHtml(item.title)}</div>
          <div class="flex gap-2 text-xs mt-0.5">${year}${rating}</div>
          <div class="flex flex-wrap gap-1 mt-1">${genres}</div>
          ${desc}
          ${addBtn}
        </div>
      </div>
    `;
  }

  // -------------------------------------------------------------------------
  // Add to library
  // -------------------------------------------------------------------------

  window._mediaAddToLibrary = async function (item) {
    // Find the button that was clicked
    const btn = event && event.target;
    if (btn) {
      btn.disabled = true;
      btn.textContent = '…';
    }

    try {
      const csrfToken = getCookie('csrftoken');
      const res = await fetch('/api/media/add/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(csrfToken ? { 'X-CSRFToken': csrfToken } : {}),
        },
        body: JSON.stringify({
          media_type: item.type,
          title: item.title,
          year: item.year,
          tmdb_id: item.tmdb_id,
          anilist_id: item.anilist_id,
          mal_id: item.mal_id,
        }),
      });
      const data = await res.json();
      if (btn) {
        btn.textContent = data.success ? '✓ Added' : '✗ Error';
        btn.className = btn.className.replace('bg-primary', data.success ? 'bg-success' : 'bg-danger');
      }
    } catch (e) {
      if (btn) {
        btn.textContent = '✗ Error';
      }
    }
  };

  // -------------------------------------------------------------------------
  // Load more
  // -------------------------------------------------------------------------

  function setupLoadMore() {
    const btn = document.getElementById('load-more-btn');
    if (!btn) return;
    btn.addEventListener('click', () => {
      const type = btn.dataset.type || currentType;
      const nextPage = parseInt(btn.dataset.nextPage || '2', 10);
      currentPage = nextPage;
      loadMediaFeed(type, nextPage, true);
    });
  }

  // -------------------------------------------------------------------------
  // Sidebar toggle
  // -------------------------------------------------------------------------

  function toggleSidebar() {
    const sidebar = document.getElementById('media-sidebar');
    const arrow = document.getElementById('sidebar-arrow');
    if (!sidebar) return;

    const collapsed = sidebar.classList.contains('w-0');
    if (collapsed) {
      sidebar.classList.remove('w-0', 'overflow-hidden');
      sidebar.classList.add('w-80');
      if (arrow) arrow.style.transform = '';
      localStorage.setItem('mediaSidebarCollapsed', 'false');
      loadInitialFeed();
    } else {
      sidebar.classList.remove('w-80');
      sidebar.classList.add('w-0', 'overflow-hidden');
      if (arrow) arrow.style.transform = 'rotate(180deg)';
      localStorage.setItem('mediaSidebarCollapsed', 'true');
    }
  }

  function setupToggle() {
    const btn = document.getElementById('sidebar-toggle');
    if (btn) btn.addEventListener('click', toggleSidebar);
  }

  function restoreSidebarState() {
    const collapsed = localStorage.getItem('mediaSidebarCollapsed') === 'true';
    if (collapsed) {
      const sidebar = document.getElementById('media-sidebar');
      const arrow = document.getElementById('sidebar-arrow');
      if (sidebar) {
        sidebar.classList.remove('w-80');
        sidebar.classList.add('w-0', 'overflow-hidden');
      }
      if (arrow) arrow.style.transform = 'rotate(180deg)';
    }
  }

  // -------------------------------------------------------------------------
  // Utilities
  // -------------------------------------------------------------------------

  function escHtml(str) {
    if (typeof str !== 'string') return str == null ? '' : String(str);
    return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  function getCookie(name) {
    const match = document.cookie.match(new RegExp('(?:^|; )' + name + '=([^;]*)'));
    return match ? decodeURIComponent(match[1]) : null;
  }

  // -------------------------------------------------------------------------
  // Boot
  // -------------------------------------------------------------------------

  document.addEventListener('DOMContentLoaded', initMediaFeed);
})();
