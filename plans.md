# Media Discovery Feed Sidebar — Implementation Plan
# HomeLab-Dashboard
## Overview
Add a collapsible left-sidebar to the dashboard with a scrollable feed of
movies, TV shows, and anime. Integrates with TMDb (movies/TV), AniList + MAL
(anime), and Radarr/Sonarr for library filtering and one-click "Add" actions.
With no Radarr/Sonarr configured: shows trending/latest only, no Recommended
tab, no Add buttons.
## Key Decisions
- Radarr/Sonarr via env vars (RADARR_URL, RADARR_API_KEY, SONARR_URL, SONARR_API_KEY)
- TMDb via TMDB_API_KEY env var (graceful fallback if not set)
- AniList primary anime source (free, no key); MAL supplementary via MAL_CLIENT_ID
- Sidebar is collapsible with toggle button, state persisted in localStorage
- No new DB models — Django in-memory cache only
- requests already in requirements.txt
## Cache Key Reference
| Data                        | TTL                       | Cache key               |
|-----------------------------|---------------------------|-------------------------|
| TMDb/AniList/MAL feed       | 6h (MEDIA_FEED_CACHE_TTL) | media_feed_{type}_{page}|
| Radarr/Sonarr library IDs   | 15m (MEDIA_LIBRARY_CACHE_TTL) | radarr_library_ids / sonarr_library_ids |
| Genre profile from library  | 15m                       | radarr_genre_profile / sonarr_genre_profile |
| TMDb genre lists            | 24h (hardcoded)           | tmdb_movie_genres / tmdb_tv_genres |
After a successful media_add: immediately invalidate the relevant
*_library_ids cache key so the title is filtered from the next feed load.
Auto-select first available quality profile + root folder when adding
to Radarr/Sonarr (no prompt).
---
## Phase 1 — Settings & Configuration [DONE]
File: homelab_dashboard/settings.py
Added at bottom:
- TMDB_API_KEY = os.environ.get('TMDB_API_KEY', '')
- RADARR_URL = os.environ.get('RADARR_URL', '').rstrip('/')
- RADARR_API_KEY = os.environ.get('RADARR_API_KEY', '')
- SONARR_URL = os.environ.get('SONARR_URL', '').rstrip('/')
- SONARR_API_KEY = os.environ.get('SONARR_API_KEY', '')
- MAL_CLIENT_ID = os.environ.get('MAL_CLIENT_ID', '')
- MEDIA_FEED_CACHE_TTL = int(os.environ.get('MEDIA_FEED_CACHE_TTL', '21600'))
- MEDIA_LIBRARY_CACHE_TTL = int(os.environ.get('MEDIA_LIBRARY_CACHE_TTL', '900'))
- CACHES locmem backend (guarded with: if 'CACHES' not in locals())
---
## Phase 2 — Backend Media Clients [ ]
File: dashboard/utils/media_client.py  (NEW)
5 classes:
TMDbClient
  - get_trending_movies(page)  → GET /trending/movie/week
  - get_trending_tv(page)      → GET /trending/tv/week
  - get_recommendations_movies(genre_ids, exclude_ids, page)  → GET /discover/movie
  - get_recommendations_tv(genre_ids, exclude_ids, page)      → GET /discover/tv
  - get_movie_genres()         → GET /genre/movie/list  (24h cache)
  - get_tv_genres()            → GET /genre/tv/list     (24h cache)
  - poster_url(path)           → https://image.tmdb.org/t/p/w342{path}
AniListClient
  - get_trending_anime(page)              → GraphQL POST to graphql.anilist.co
  - get_seasonal_anime(year, season, page)→ GraphQL POST to graphql.anilist.co
MALClient
  - get_anime_ranking(type, limit, offset) → GET /v2/anime/ranking
    with X-MAL-CLIENT-ID header
RadarrClient
  - get_library()              → GET /api/v3/movie
  - lookup_movie(tmdb_id)      → GET /api/v3/movie/lookup/tmdb
  - add_movie(title, tmdb_id, year)
  - get_quality_profiles()     → GET /api/v3/qualityprofile
  - get_root_folders()         → GET /api/v3/rootfolder
SonarrClient
  - get_library()              → GET /api/v3/series
  - lookup_series(query)       → GET /api/v3/series/lookup
  - add_series(title, year, tmdb_id)
  - get_quality_profiles()     → GET /api/v3/qualityprofile
  - get_root_folders()         → GET /api/v3/rootfolder
  - get_language_profiles()    → GET /api/v3/languageprofile
Module-level helpers:
get_media_feed(filter_type, page)
  - filter_type: 'movies' | 'tv' | 'anime' | 'recommended' | 'all'
  - Aggregates + normalises from all sources
  - Filters items already in Radarr/Sonarr library
  - Two-tier caching
  - Returns: {items: [...], has_more: bool}
  Normalised item shape:
  {
    id: str,          # e.g. 'movie_123', 'tv_456', 'anime_789'
    type: str,        # 'movie' | 'tv' | 'anime'
    title: str,
    year: int|None,
    rating: float|None,   # out of 10
    poster_url: str|None,
    description: str|None,
    genres: [str],
    tmdb_id: int|None,
    anilist_id: int|None,
    mal_id: int|None,
    in_library: bool,     # true if already in Radarr (movie) or Sonarr (tv/anime)
  }
get_media_status()
  - Returns {tmdb_available, radarr_available, sonarr_available, mal_available}
  - 5-minute cache
---
## Phase 3 — API Endpoints [ ]
Files: dashboard/views.py, dashboard/urls.py
3 new view functions in views.py:
media_feed(request)
  GET /api/media/feed/?type=&page=
  Returns: {items, has_more, status}
media_status(request)
  GET /api/media/status/
  Returns: {tmdb_available, radarr_available, sonarr_available, mal_available}
media_add(request)
  POST /api/media/add/
  Body: {media_type, title, year, tmdb_id?, anilist_id?, mal_id?}
  - movie → Radarr, invalidates radarr_library_ids cache
  - tv/anime → Sonarr, invalidates sonarr_library_ids cache
  Returns: {success, message} or {success, error}
3 new URL patterns in dashboard/urls.py:
  path('api/media/feed/',   views.media_feed,   name='media_feed'),
  path('api/media/status/', views.media_status, name='media_status'),
  path('api/media/add/',    views.media_add,    name='media_add'),
---
## Phase 4 — base.html Layout [ ]
File: templates/base.html
Wrap existing <main> and <footer> in a new block:
  {% block main_area %}
    <main class="py-8">...</main>
    <footer>...</footer>
  {% endblock %}
Other pages (service_detail, grafana) inherit the default and are unaffected.
---
## Phase 5 — Dashboard Template [ ]
File: templates/dashboard/index.html
Override {% block main_area %} with a calc(100vh - 73px) flex container:
  <div class="flex overflow-hidden" style="height: calc(100vh - 73px);">
    <!-- Left sidebar -->
    <aside id="media-sidebar"
           class="flex flex-col bg-bg-secondary border-r border-border
                  transition-all duration-300 w-80 shrink-0 overflow-hidden">
      <!-- Tab bar: Recommended (hidden by default) | Movies | TV Shows | Anime -->
      <!-- Scrollable feed list: <div id="media-feed-list"> -->
      <!-- Load More button pinned at bottom -->
    </aside>
    <!-- Toggle button sitting on sidebar border -->
    <div class="relative shrink-0 flex items-center">
      <button id="sidebar-toggle" class="w-5 h-12 bg-bg-secondary border-y
              border-r border-border rounded-r-lg flex items-center
              justify-center hover:bg-bg-card transition-colors">
        <svg id="sidebar-arrow"><!-- left/right chevron --></svg>
      </button>
    </div>
    <!-- Main content (all existing dashboard content) -->
    <main class="flex-1 overflow-y-auto py-8">
      <div class="max-w-screen-2xl mx-auto px-5">
        <!-- stats cards, grafana panels, services grid, modals -->
      </div>
    </main>
  </div>
Card layout inside #media-feed-list:
  - w-16 h-24 poster thumbnail
  - title (truncated), year, ⭐ rating
  - genre pill tags
  - 2-line clamped description
  - conditional "Add to Radarr" / "Add to Sonarr" button
---
## Phase 6 — Frontend JavaScript [ ]
File: static/js/media_feed.js  (NEW)
Loaded via {% block extra_js %} in index.html
Functions:
initMediaFeed()
  - Calls /api/media/status/
  - Shows Recommended tab only if radarr_available || sonarr_available
  - Restores localStorage sidebar collapse state
  - Loads page 1 of the active tab
loadMediaFeed(type, page, append)
  - Shows skeleton cards while loading
  - Fetches /api/media/feed/?type=&page=
  - Renders cards, updates Load More button visibility
renderMediaCard(item, showAddButton)
  - Builds and returns card HTML string
addToLibrary(item)
  - POST /api/media/add/ with CSRF token
  - Button states: idle → loading → ✓ Added / ✗ Error
toggleSidebar()
  - Toggles w-80 / w-0 + overflow-hidden on #media-sidebar
  - Flips arrow direction on #sidebar-arrow
  - Persists state to localStorage key 'mediaSidebarCollapsed'
---
## Phase 7 — Tests [ ]
File: tests/test_utilities.py  (add class TestMediaClient)
Unit tests with mocked HTTP:
  - test_tmdb_client_trending_movies_cached
  - test_anilist_client_trending_anime
  - test_radarr_client_get_library
  - test_sonarr_client_get_library
  - test_get_media_status_all_unavailable
  - test_get_media_feed_movies_no_tmdb_key
  - test_get_media_feed_anime_anilist_only
API endpoint tests (can go in test_views.py):
  - test_media_feed_endpoint_returns_json
  - test_media_status_endpoint
  - test_media_add_requires_post
---
## Verification Checklist
  [ ] python manage.py check passes (no new models, no migration needed)
  [ ] All 3 API endpoints return correct JSON shapes
  [ ] Sidebar loads on left, cards render, tabs switch content
  [ ] Collapse/expand persists across page reload
  [ ] No env vars set → only AniList trending shown (graceful fallback)
  [ ] service_detail and grafana pages visually unchanged
---
Ready to implement whenever you switch out of plan mode. We'll go phase by phase and I'll stop after each one.