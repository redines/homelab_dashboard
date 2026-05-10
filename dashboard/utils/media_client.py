"""
Media discovery clients for TMDb, AniList, MAL, Radarr, and Sonarr.
"""
import logging
import requests
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

TMDB_BASE = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/w342"
ANILIST_URL = "https://graphql.anilist.co"
MAL_BASE = "https://api.myanimelist.net/v2"
PAGE_SIZE = 20


# ---------------------------------------------------------------------------
# TMDb
# ---------------------------------------------------------------------------

class TMDbClient:
    def __init__(self):
        self.api_key = getattr(settings, 'TMDB_API_KEY', '')

    def _get(self, path, params=None):
        if not self.api_key:
            return None
        p = {'api_key': self.api_key}
        if params:
            p.update(params)
        try:
            r = requests.get(f"{TMDB_BASE}{path}", params=p, timeout=10)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            logger.warning(f"TMDb request failed: {e}")
            return None

    def get_trending_movies(self, page=1):
        return self._get('/trending/movie/week', {'page': page})

    def get_trending_tv(self, page=1):
        return self._get('/trending/tv/week', {'page': page})

    def get_recommendations_movies(self, genre_ids=None, exclude_ids=None, page=1):
        params = {'page': page, 'sort_by': 'popularity.desc'}
        if genre_ids:
            params['with_genres'] = ','.join(str(g) for g in genre_ids)
        if exclude_ids:
            params['without_ids'] = ','.join(str(i) for i in exclude_ids)
        return self._get('/discover/movie', params)

    def get_recommendations_tv(self, genre_ids=None, exclude_ids=None, page=1):
        params = {'page': page, 'sort_by': 'popularity.desc'}
        if genre_ids:
            params['with_genres'] = ','.join(str(g) for g in genre_ids)
        if exclude_ids:
            params['without_ids'] = ','.join(str(i) for i in exclude_ids)
        return self._get('/discover/tv', params)

    def get_movie_genres(self):
        key = 'tmdb_movie_genres'
        cached = cache.get(key)
        if cached is not None:
            return cached
        data = self._get('/genre/movie/list')
        if data:
            cache.set(key, data, 86400)
        return data

    def get_tv_genres(self):
        key = 'tmdb_tv_genres'
        cached = cache.get(key)
        if cached is not None:
            return cached
        data = self._get('/genre/tv/list')
        if data:
            cache.set(key, data, 86400)
        return data

    def poster_url(self, path):
        if not path:
            return None
        return f"{TMDB_IMAGE_BASE}{path}"


# ---------------------------------------------------------------------------
# AniList
# ---------------------------------------------------------------------------

class AniListClient:
    TRENDING_QUERY = """
    query ($page: Int, $perPage: Int) {
      Page(page: $page, perPage: $perPage) {
        pageInfo { hasNextPage }
        media(type: ANIME, sort: TRENDING_DESC, status_not: NOT_YET_RELEASED) {
          id idMal title { romaji english } startDate { year }
          averageScore coverImage { large } description(asHtml: false)
          genres episodes
        }
      }
    }
    """

    SEASONAL_QUERY = """
    query ($page: Int, $perPage: Int, $year: Int, $season: MediaSeason) {
      Page(page: $page, perPage: $perPage) {
        pageInfo { hasNextPage }
        media(type: ANIME, sort: POPULARITY_DESC, seasonYear: $year, season: $season) {
          id idMal title { romaji english } startDate { year }
          averageScore coverImage { large } description(asHtml: false)
          genres episodes
        }
      }
    }
    """

    def _post(self, query, variables):
        try:
            r = requests.post(ANILIST_URL, json={'query': query, 'variables': variables}, timeout=10)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            logger.warning(f"AniList request failed: {e}")
            return None

    def get_trending_anime(self, page=1):
        return self._post(self.TRENDING_QUERY, {'page': page, 'perPage': PAGE_SIZE})

    def get_seasonal_anime(self, year, season, page=1):
        return self._post(self.SEASONAL_QUERY, {'page': page, 'perPage': PAGE_SIZE, 'year': year, 'season': season})


# ---------------------------------------------------------------------------
# MAL
# ---------------------------------------------------------------------------

class MALClient:
    def __init__(self):
        self.client_id = getattr(settings, 'MAL_CLIENT_ID', '')

    def _get(self, path, params=None):
        if not self.client_id:
            return None
        headers = {'X-MAL-CLIENT-ID': self.client_id}
        try:
            r = requests.get(f"{MAL_BASE}{path}", params=params, headers=headers, timeout=10)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            logger.warning(f"MAL request failed: {e}")
            return None

    def get_anime_ranking(self, ranking_type='all', limit=PAGE_SIZE, offset=0):
        return self._get('/anime/ranking', {
            'ranking_type': ranking_type,
            'limit': limit,
            'offset': offset,
            'fields': 'id,title,main_picture,start_date,mean,genres,synopsis,num_episodes',
        })


# ---------------------------------------------------------------------------
# Radarr
# ---------------------------------------------------------------------------

class RadarrClient:
    def __init__(self):
        self.url = getattr(settings, 'RADARR_URL', '').rstrip('/')
        self.api_key = getattr(settings, 'RADARR_API_KEY', '')

    def _get(self, path, params=None):
        if not self.url or not self.api_key:
            return None
        headers = {'X-Api-Key': self.api_key}
        try:
            r = requests.get(f"{self.url}{path}", params=params, headers=headers, timeout=10)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            logger.warning(f"Radarr request failed: {e}")
            return None

    def _post(self, path, body):
        if not self.url or not self.api_key:
            return None
        headers = {'X-Api-Key': self.api_key, 'Content-Type': 'application/json'}
        import json
        try:
            r = requests.post(f"{self.url}{path}", json=body, headers=headers, timeout=10)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            logger.warning(f"Radarr POST failed: {e}")
            return None

    def get_library(self):
        return self._get('/api/v3/movie')

    def lookup_movie(self, tmdb_id):
        return self._get('/api/v3/movie/lookup/tmdb', {'tmdbId': tmdb_id})

    def get_quality_profiles(self):
        return self._get('/api/v3/qualityprofile')

    def get_root_folders(self):
        return self._get('/api/v3/rootfolder')

    def add_movie(self, title, tmdb_id, year):
        profiles = self.get_quality_profiles()
        roots = self.get_root_folders()
        if not profiles or not roots:
            return None
        profile_id = profiles[0]['id']
        root_path = roots[0]['path']
        return self._post('/api/v3/movie', {
            'title': title,
            'tmdbId': tmdb_id,
            'year': year,
            'qualityProfileId': profile_id,
            'rootFolderPath': root_path,
            'monitored': True,
            'addOptions': {'searchForMovie': True},
        })


# ---------------------------------------------------------------------------
# Sonarr
# ---------------------------------------------------------------------------

class SonarrClient:
    def __init__(self):
        self.url = getattr(settings, 'SONARR_URL', '').rstrip('/')
        self.api_key = getattr(settings, 'SONARR_API_KEY', '')

    def _get(self, path, params=None):
        if not self.url or not self.api_key:
            return None
        headers = {'X-Api-Key': self.api_key}
        try:
            r = requests.get(f"{self.url}{path}", params=params, headers=headers, timeout=10)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            logger.warning(f"Sonarr request failed: {e}")
            return None

    def _post(self, path, body):
        if not self.url or not self.api_key:
            return None
        headers = {'X-Api-Key': self.api_key, 'Content-Type': 'application/json'}
        try:
            r = requests.post(f"{self.url}{path}", json=body, headers=headers, timeout=10)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            logger.warning(f"Sonarr POST failed: {e}")
            return None

    def get_library(self):
        return self._get('/api/v3/series')

    def lookup_series(self, query):
        return self._get('/api/v3/series/lookup', {'term': query})

    def get_quality_profiles(self):
        return self._get('/api/v3/qualityprofile')

    def get_root_folders(self):
        return self._get('/api/v3/rootfolder')

    def get_language_profiles(self):
        return self._get('/api/v3/languageprofile')

    def add_series(self, title, year, tvdb_id):
        profiles = self.get_quality_profiles()
        roots = self.get_root_folders()
        lang_profiles = self.get_language_profiles()
        if not profiles or not roots:
            return None
        profile_id = profiles[0]['id']
        root_path = roots[0]['path']
        body = {
            'title': title,
            'tvdbId': tvdb_id,
            'year': year,
            'qualityProfileId': profile_id,
            'rootFolderPath': root_path,
            'monitored': True,
            'addOptions': {'searchForMissingEpisodes': True},
            'seasons': [],
        }
        if lang_profiles:
            body['languageProfileId'] = lang_profiles[0]['id']
        return self._post('/api/v3/series', body)


# ---------------------------------------------------------------------------
# Normalization helpers
# ---------------------------------------------------------------------------

def _normalize_tmdb_movie(item, genre_map, in_library_ids):
    tmdb_id = item.get('id')
    return {
        'id': f"movie_{tmdb_id}",
        'type': 'movie',
        'title': item.get('title') or item.get('original_title', ''),
        'year': int(item['release_date'][:4]) if item.get('release_date') else None,
        'rating': item.get('vote_average'),
        'poster_url': TMDbClient().poster_url(item.get('poster_path')),
        'description': item.get('overview'),
        'genres': [genre_map.get(gid, '') for gid in (item.get('genre_ids') or []) if genre_map.get(gid)],
        'tmdb_id': tmdb_id,
        'anilist_id': None,
        'mal_id': None,
        'in_library': tmdb_id in in_library_ids.get('radarr', set()),
    }


def _normalize_tmdb_tv(item, genre_map, in_library_ids):
    tmdb_id = item.get('id')
    return {
        'id': f"tv_{tmdb_id}",
        'type': 'tv',
        'title': item.get('name') or item.get('original_name', ''),
        'year': int(item['first_air_date'][:4]) if item.get('first_air_date') else None,
        'rating': item.get('vote_average'),
        'poster_url': TMDbClient().poster_url(item.get('poster_path')),
        'description': item.get('overview'),
        'genres': [genre_map.get(gid, '') for gid in (item.get('genre_ids') or []) if genre_map.get(gid)],
        'tmdb_id': tmdb_id,
        'anilist_id': None,
        'mal_id': None,
        'in_library': tmdb_id in in_library_ids.get('sonarr_tmdb', set()),
    }


def _normalize_anilist(item, in_library_ids):
    title = item.get('title', {})
    al_id = item.get('id')
    mal_id = item.get('idMal')
    score = item.get('averageScore')
    cover = (item.get('coverImage') or {}).get('large')
    year = (item.get('startDate') or {}).get('year')
    desc = item.get('description') or ''
    # Strip HTML tags simply
    import re
    desc = re.sub(r'<[^>]+>', '', desc)
    return {
        'id': f"anime_{al_id}",
        'type': 'anime',
        'title': title.get('english') or title.get('romaji') or '',
        'year': year,
        'rating': round(score / 10, 1) if score else None,
        'poster_url': cover,
        'description': desc[:300] if desc else None,
        'genres': item.get('genres') or [],
        'tmdb_id': None,
        'anilist_id': al_id,
        'mal_id': mal_id,
        'in_library': mal_id in in_library_ids.get('sonarr_mal', set()) or al_id in in_library_ids.get('sonarr_anilist', set()),
    }


def _normalize_mal(item, in_library_ids):
    node = item.get('node', item)
    mal_id = node.get('id')
    pic = (node.get('main_picture') or {}).get('medium')
    genres = [g['name'] for g in (node.get('genres') or [])]
    start = node.get('start_date', '')
    year = int(start[:4]) if start and len(start) >= 4 else None
    score = node.get('mean')
    return {
        'id': f"anime_mal_{mal_id}",
        'type': 'anime',
        'title': node.get('title', ''),
        'year': year,
        'rating': score,
        'poster_url': pic,
        'description': node.get('synopsis'),
        'genres': genres,
        'tmdb_id': None,
        'anilist_id': None,
        'mal_id': mal_id,
        'in_library': mal_id in in_library_ids.get('sonarr_mal', set()),
    }


# ---------------------------------------------------------------------------
# Library ID sets (cached)
# ---------------------------------------------------------------------------

def _get_library_ids():
    cache_key = 'media_library_ids'
    ttl = getattr(settings, 'MEDIA_LIBRARY_CACHE_TTL', 900)
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    result = {'radarr': set(), 'sonarr_tmdb': set(), 'sonarr_mal': set(), 'sonarr_anilist': set()}

    radarr = RadarrClient()
    library = radarr.get_library()
    if library:
        result['radarr'] = {m.get('tmdbId') for m in library if m.get('tmdbId')}

    sonarr = SonarrClient()
    series = sonarr.get_library()
    if series:
        for s in series:
            if s.get('tmdbId'):
                result['sonarr_tmdb'].add(s['tmdbId'])

    cache.set(cache_key, result, ttl)
    return result


def invalidate_radarr_cache():
    cache.delete('media_library_ids')
    cache.delete('radarr_library_ids')


def invalidate_sonarr_cache():
    cache.delete('media_library_ids')
    cache.delete('sonarr_library_ids')


# ---------------------------------------------------------------------------
# Genre profile builder for recommendations
# ---------------------------------------------------------------------------

def _build_genre_profile():
    """Return list of popular genre IDs from Radarr/Sonarr libraries via TMDb."""
    from collections import Counter
    genre_counter = Counter()

    radarr = RadarrClient()
    movies = radarr.get_library() or []
    for m in movies[:50]:
        for gid in (m.get('genres') or []):
            if isinstance(gid, dict):
                genre_counter[gid.get('tmdbId') or gid.get('id')] += 1
            else:
                genre_counter[gid] += 1

    # Return top 3 genre IDs (non-None)
    return [gid for gid, _ in genre_counter.most_common(3) if gid]


# ---------------------------------------------------------------------------
# Main feed function
# ---------------------------------------------------------------------------

def get_media_feed(filter_type='all', page=1):
    cache_key = f'media_feed_{filter_type}_{page}'
    ttl = getattr(settings, 'MEDIA_FEED_CACHE_TTL', 21600)
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    in_library_ids = _get_library_ids()
    tmdb = TMDbClient()

    # Build genre maps
    movie_genres = {}
    tv_genres = {}
    if tmdb.api_key:
        mg = tmdb.get_movie_genres()
        if mg:
            movie_genres = {g['id']: g['name'] for g in mg.get('genres', [])}
        tg = tmdb.get_tv_genres()
        if tg:
            tv_genres = {g['id']: g['name'] for g in tg.get('genres', [])}

    items = []
    has_more = False

    if filter_type == 'movies':
        data = tmdb.get_trending_movies(page) if tmdb.api_key else None
        if data:
            for item in data.get('results', []):
                items.append(_normalize_tmdb_movie(item, movie_genres, in_library_ids))
            has_more = data.get('page', 1) < data.get('total_pages', 1)

    elif filter_type == 'tv':
        data = tmdb.get_trending_tv(page) if tmdb.api_key else None
        if data:
            for item in data.get('results', []):
                items.append(_normalize_tmdb_tv(item, tv_genres, in_library_ids))
            has_more = data.get('page', 1) < data.get('total_pages', 1)

    elif filter_type == 'anime':
        anilist = AniListClient()
        data = anilist.get_trending_anime(page)
        if data:
            page_data = data.get('data', {}).get('Page', {})
            for item in page_data.get('media', []):
                items.append(_normalize_anilist(item, in_library_ids))
            has_more = page_data.get('pageInfo', {}).get('hasNextPage', False)

        # Supplement with MAL if available and on page 1
        mal = MALClient()
        if mal.client_id and page == 1:
            mal_data = mal.get_anime_ranking(ranking_type='all', limit=10, offset=0)
            if mal_data:
                existing_mal_ids = {i['mal_id'] for i in items if i['mal_id']}
                for entry in (mal_data.get('data') or []):
                    node = entry.get('node', entry)
                    if node.get('id') not in existing_mal_ids:
                        items.append(_normalize_mal(entry, in_library_ids))

    elif filter_type == 'recommended':
        genre_ids = _build_genre_profile()
        radarr_ids = list(in_library_ids.get('radarr', set()))
        sonarr_ids = list(in_library_ids.get('sonarr_tmdb', set()))

        if tmdb.api_key:
            movie_data = tmdb.get_recommendations_movies(genre_ids=genre_ids, exclude_ids=radarr_ids, page=page)
            if movie_data:
                for item in movie_data.get('results', [])[:10]:
                    items.append(_normalize_tmdb_movie(item, movie_genres, in_library_ids))
                has_more = has_more or (movie_data.get('page', 1) < movie_data.get('total_pages', 1))

            tv_data = tmdb.get_recommendations_tv(genre_ids=genre_ids, exclude_ids=sonarr_ids, page=page)
            if tv_data:
                for item in tv_data.get('results', [])[:10]:
                    items.append(_normalize_tmdb_tv(item, tv_genres, in_library_ids))
                has_more = has_more or (tv_data.get('page', 1) < tv_data.get('total_pages', 1))

    else:  # 'all'
        per_source = PAGE_SIZE // 3
        remainder = PAGE_SIZE - per_source * 3

        if tmdb.api_key:
            movie_data = tmdb.get_trending_movies(page)
            if movie_data:
                for item in movie_data.get('results', [])[:per_source + remainder]:
                    items.append(_normalize_tmdb_movie(item, movie_genres, in_library_ids))
                has_more = has_more or (movie_data.get('page', 1) < movie_data.get('total_pages', 1))

            tv_data = tmdb.get_trending_tv(page)
            if tv_data:
                for item in tv_data.get('results', [])[:per_source]:
                    items.append(_normalize_tmdb_tv(item, tv_genres, in_library_ids))
                has_more = has_more or (tv_data.get('page', 1) < tv_data.get('total_pages', 1))

        anilist = AniListClient()
        anime_data = anilist.get_trending_anime(page)
        if anime_data:
            page_data = anime_data.get('data', {}).get('Page', {})
            for item in page_data.get('media', [])[:per_source]:
                items.append(_normalize_anilist(item, in_library_ids))
            has_more = has_more or page_data.get('pageInfo', {}).get('hasNextPage', False)

    result = {'items': items, 'has_more': has_more}
    cache.set(cache_key, result, ttl)
    return result


# ---------------------------------------------------------------------------
# Status check
# ---------------------------------------------------------------------------

def get_media_status():
    cache_key = 'media_status'
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    status = {
        'tmdb_available': False,
        'radarr_available': False,
        'sonarr_available': False,
        'mal_available': False,
    }

    tmdb = TMDbClient()
    if tmdb.api_key:
        data = tmdb.get_trending_movies(1)
        status['tmdb_available'] = data is not None

    radarr = RadarrClient()
    if radarr.url and radarr.api_key:
        data = radarr.get_quality_profiles()
        status['radarr_available'] = data is not None

    sonarr = SonarrClient()
    if sonarr.url and sonarr.api_key:
        data = sonarr.get_quality_profiles()
        status['sonarr_available'] = data is not None

    mal = MALClient()
    if mal.client_id:
        data = mal.get_anime_ranking(ranking_type='all', limit=1, offset=0)
        status['mal_available'] = data is not None

    cache.set(cache_key, status, 300)
    return status
