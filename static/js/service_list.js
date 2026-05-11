/**
 * Service list helpers
 *  - Loads qBittorrent torrent-count stats into each qBittorrent service row.
 *  - Drives the Torrent Queue Cleanup widget.
 */

(function () {
  'use strict';

  // ---------------------------------------------------------------------------
  // qBittorrent inline stats
  // ---------------------------------------------------------------------------

  /**
   * Render a small stat pill.
   */
  function statPill(icon, count, label, colour) {
    return `<span class="inline-flex items-center gap-1 ${colour}" title="${label}">
              ${icon} <span class="font-semibold">${count}</span>
            </span>`;
  }

  async function loadQbStats(serviceId) {
    const el = document.getElementById(`qb-stats-${serviceId}`);
    if (!el) return;

    try {
      const res = await fetch(`/api/services/${serviceId}/qb-stats/`);
      const data = await res.json();

      if (!data.success) {
        el.innerHTML = `<span class="text-warning text-xs">Stats unavailable</span>`;
        return;
      }

      const s = data.stats;
      el.innerHTML = [
        statPill('\u2b07\ufe0f', s.downloading, 'Downloading', 'text-primary'),
        statPill('\u2b06\ufe0f', s.uploading,   'Uploading',   'text-success'),
        statPill('\ud83c\udf31', s.seeding,     'Seeding',     'text-blue-400'),
        statPill('\u2705', s.completed,   'Completed',   'text-text-secondary'),
        `<span class="text-text-secondary">/ ${s.total} total</span>`,
      ].join('');
    } catch (_) {
      el.innerHTML = '';
    }
  }

  // ---------------------------------------------------------------------------
  // Torrent cleanup widget
  // ---------------------------------------------------------------------------

  async function initCleanupWidget() {
    try {
      const res = await fetch('/api/torrent-cleanup/status/');
      const data = await res.json();
      if (!data.available) return;

      const section = document.getElementById('torrent-cleanup-section');
      if (section) section.classList.remove('hidden');

      document.getElementById('cleanup-dry-run-btn').addEventListener('click', () => runCleanup(true));
      document.getElementById('cleanup-run-btn').addEventListener('click', () => {
        if (confirm('This will delete completed & imported torrents and their source files from qBittorrent. Continue?')) {
          runCleanup(false);
        }
      });
    } catch (_) {
      // Cleanup not available — silently skip
    }
  }

  async function runCleanup(dryRun) {
    const resultEl = document.getElementById('cleanup-result');
    const dryBtn   = document.getElementById('cleanup-dry-run-btn');
    const runBtn   = document.getElementById('cleanup-run-btn');

    resultEl.classList.remove('hidden');
    resultEl.innerHTML = '<span class="text-text-secondary">Running\u2026</span>';
    [dryBtn, runBtn].forEach(b => b.disabled = true);

    try {
      const res = await fetch('/api/torrent-cleanup/run/', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({dry_run: dryRun}),
      });
      const data = await res.json();

      if (!data.success) {
        resultEl.innerHTML = `<span class="text-danger">${data.error || 'Unknown error'}</span>`;
        return;
      }

      const lines = [
        `<span class="text-text-secondary">${dryRun ? 'DRY RUN — ' : ''}Checked: ${data.checked} | Cleaned: ${data.cleaned} | Skipped: ${data.skipped} | Errors: ${data.errors}</span>`,
        ...data.details.map(line => {
          const cls = line.startsWith('DELETE') || line.startsWith('DRY-RUN') ? 'text-success'
                    : line.startsWith('ERROR') ? 'text-danger'
                    : 'text-text-secondary';
          return `<div class="${cls}">${line}</div>`;
        }),
      ];
      resultEl.innerHTML = lines.join('');
    } catch (err) {
      resultEl.innerHTML = `<span class="text-danger">${err.message}</span>`;
    } finally {
      [dryBtn, runBtn].forEach(b => b.disabled = false);
    }
  }

  // ---------------------------------------------------------------------------
  // Boot
  // ---------------------------------------------------------------------------

  function init() {
    document.querySelectorAll('[id^="qb-stats-"]').forEach(function (el) {
      const serviceId = el.id.replace('qb-stats-', '');
      loadQbStats(serviceId);
    });

    initCleanupWidget();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
