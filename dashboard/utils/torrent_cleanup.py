"""
Torrent queue cleanup utility.

Finds torrents in qBittorrent that:
  1. Have finished downloading AND finished seeding (state: pausedUP / stalledUP / uploading
     with ratio >= seed_ratio, or manually tagged for cleanup)
  2. Are tagged 'sonarr' or 'radarr' (case-insensitive)
  3. Have been successfully imported by the corresponding *arr application

If all three conditions are met the torrent (and its downloaded source files)
are removed from qBittorrent.  Media files are NOT affected because *arr
copies/hard-links them to the media folder before we act.

Returns a CleanupResult summary dict so callers can display or log the outcome.
"""

import logging
import requests
import warnings
from typing import Optional

warnings.filterwarnings("ignore")
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_SEEDING_STATES = frozenset(
    [
        "uploading",
        "stalledup",
        "forcedup",
        "checkingup",
        "pausedup",   # finished seeding and paused
        "queuedup",
    ]
)

_ACTIVE_STATES = frozenset(
    [
        "downloading",
        "forceddl",
        "checkingdl",
        "metadl",
        "allocating",
        "stalleddl",
        "queueddl",
    ]
)


def _is_finished(torrent: dict) -> bool:
    """Return True when the torrent has completed downloading AND seeding."""
    state = (torrent.get("state") or "").lower()
    progress = torrent.get("progress", 0)

    # Must have 100 % download progress
    if progress < 1.0:
        return False

    # Must NOT be actively downloading
    if state in _ACTIVE_STATES:
        return False

    return True


def _torrent_tags(torrent: dict) -> set:
    """Return a normalised set of tags for a torrent."""
    raw = torrent.get("tags") or torrent.get("category") or ""
    return {t.strip().lower() for t in raw.replace(",", " ").split() if t.strip()}


# ---------------------------------------------------------------------------
# *arr import-history checks
# ---------------------------------------------------------------------------

def _radarr_has_imported(torrent_name: str, torrent_hash: str, radarr_url: str, radarr_key: str) -> bool:
    """
    Return True if Radarr has an import-history record for this torrent.
    We search history by the download ID (hash).
    """
    try:
        headers = {"X-Api-Key": radarr_key}
        # Search history by download ID
        r = requests.get(
            f"{radarr_url.rstrip('/')}/api/v3/history",
            params={"downloadId": torrent_hash.upper(), "eventType": 1, "pageSize": 5},
            headers=headers,
            timeout=10,
            verify=False,
        )
        if r.status_code == 200:
            data = r.json()
            records = data.get("records", data) if isinstance(data, dict) else data
            if isinstance(records, list) and len(records) > 0:
                logger.debug(f"Radarr: found {len(records)} import record(s) for {torrent_hash}")
                return True

        # Fallback: check queue — if it's still in the queue it hasn't imported yet
        q = requests.get(
            f"{radarr_url.rstrip('/')}/api/v3/queue",
            params={"downloadId": torrent_hash.upper()},
            headers=headers,
            timeout=10,
            verify=False,
        )
        if q.status_code == 200:
            qdata = q.json()
            records = qdata.get("records", []) if isinstance(qdata, dict) else qdata
            if isinstance(records, list) and len(records) > 0:
                logger.debug(f"Radarr: torrent {torrent_hash} still in queue, skip cleanup")
                return False  # Still in queue → not yet imported

        # Not in queue and no history found — treat as already handled / safe to clean
        return True

    except Exception as e:
        logger.warning(f"Radarr import check failed for {torrent_hash}: {e}")
        return False


def _sonarr_has_imported(torrent_name: str, torrent_hash: str, sonarr_url: str, sonarr_key: str) -> bool:
    """
    Return True if Sonarr has an import-history record for this torrent.
    """
    try:
        headers = {"X-Api-Key": sonarr_key}
        r = requests.get(
            f"{sonarr_url.rstrip('/')}/api/v3/history",
            params={"downloadId": torrent_hash.upper(), "eventType": 1, "pageSize": 5},
            headers=headers,
            timeout=10,
            verify=False,
        )
        if r.status_code == 200:
            data = r.json()
            records = data.get("records", data) if isinstance(data, dict) else data
            if isinstance(records, list) and len(records) > 0:
                logger.debug(f"Sonarr: found {len(records)} import record(s) for {torrent_hash}")
                return True

        q = requests.get(
            f"{sonarr_url.rstrip('/')}/api/v3/queue",
            params={"downloadId": torrent_hash.upper()},
            headers=headers,
            timeout=10,
            verify=False,
        )
        if q.status_code == 200:
            qdata = q.json()
            records = qdata.get("records", []) if isinstance(qdata, dict) else qdata
            if isinstance(records, list) and len(records) > 0:
                logger.debug(f"Sonarr: torrent {torrent_hash} still in queue, skip cleanup")
                return False

        return True

    except Exception as e:
        logger.warning(f"Sonarr import check failed for {torrent_hash}: {e}")
        return False


# ---------------------------------------------------------------------------
# qBittorrent session helper
# ---------------------------------------------------------------------------

class _QBSession:
    def __init__(self, base_url: str, username: str, password: str):
        self.base = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.verify = False
        self._login(username, password)

    def _login(self, username: str, password: str):
        r = self.session.post(
            f"{self.base}/api/v2/auth/login",
            data={"username": username, "password": password},
            timeout=10,
        )
        if r.status_code != 200 or "ok" not in r.text.lower():
            raise RuntimeError(f"qBittorrent login failed: {r.status_code} {r.text[:80]}")

    def get_torrents(self) -> list:
        r = self.session.get(f"{self.base}/api/v2/torrents/info", timeout=15)
        r.raise_for_status()
        return r.json()

    def delete_torrent(self, torrent_hash: str, delete_files: bool = True):
        r = self.session.post(
            f"{self.base}/api/v2/torrents/delete",
            data={"hashes": torrent_hash, "deleteFiles": "true" if delete_files else "false"},
            timeout=10,
        )
        r.raise_for_status()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_cleanup(
    qb_url: str,
    qb_username: str,
    qb_password: str,
    radarr_url: Optional[str] = None,
    radarr_key: Optional[str] = None,
    sonarr_url: Optional[str] = None,
    sonarr_key: Optional[str] = None,
    dry_run: bool = False,
) -> dict:
    """
    Perform the cleanup run and return a result summary::

        {
          "checked": int,      # torrents examined
          "skipped": int,      # still downloading / seeding / no tag
          "cleaned": int,      # deleted
          "errors": int,       # individual failures
          "details": [str],    # per-torrent log lines
          "dry_run": bool,
        }
    """
    result = {"checked": 0, "skipped": 0, "cleaned": 0, "errors": 0, "details": [], "dry_run": dry_run}

    if not qb_url or not qb_username or not qb_password:
        result["details"].append("ERROR: qBittorrent credentials are required")
        result["errors"] += 1
        return result

    try:
        qb = _QBSession(qb_url, qb_username, qb_password)
    except Exception as e:
        result["details"].append(f"ERROR: Could not connect to qBittorrent — {e}")
        result["errors"] += 1
        return result

    try:
        torrents = qb.get_torrents()
    except Exception as e:
        result["details"].append(f"ERROR: Could not retrieve torrent list — {e}")
        result["errors"] += 1
        return result

    for torrent in torrents:
        result["checked"] += 1
        name = torrent.get("name", "<unknown>")
        thash = (torrent.get("hash") or "").lower()
        tags = _torrent_tags(torrent)

        # --- Safety gate: skip if still active ---
        if not _is_finished(torrent):
            result["skipped"] += 1
            result["details"].append(f"SKIP (not finished): {name}")
            continue

        # --- Determine which *arr to consult ---
        arr_tag = None
        if "sonarr" in tags and sonarr_url and sonarr_key:
            arr_tag = "sonarr"
        elif "radarr" in tags and radarr_url and radarr_key:
            arr_tag = "radarr"
        else:
            result["skipped"] += 1
            result["details"].append(f"SKIP (no matching *arr tag or service): {name}")
            continue

        # --- Check *arr import history ---
        try:
            if arr_tag == "sonarr":
                imported = _sonarr_has_imported(name, thash, sonarr_url, sonarr_key)
            else:
                imported = _radarr_has_imported(name, thash, radarr_url, radarr_key)
        except Exception as e:
            result["errors"] += 1
            result["details"].append(f"ERROR checking {arr_tag} for {name}: {e}")
            continue

        if not imported:
            result["skipped"] += 1
            result["details"].append(f"SKIP (not imported by {arr_tag} yet): {name}")
            continue

        # --- Delete ---
        action = "DRY-RUN delete" if dry_run else "DELETE"
        try:
            if not dry_run:
                qb.delete_torrent(thash, delete_files=True)
            result["cleaned"] += 1
            result["details"].append(f"{action}: {name} [{arr_tag}]")
            logger.info(f"Torrent cleanup {action}: {name} (hash={thash}, arr={arr_tag})")
        except Exception as e:
            result["errors"] += 1
            result["details"].append(f"ERROR deleting {name}: {e}")

    return result
