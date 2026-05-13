/**
 * Service list helpers
 *  - Loads qBittorrent torrent-count stats into each qBittorrent service row.
 */

(function () {
  'use strict';

  // ---------------------------------------------------------------------------
  // qBittorrent inline stats
  // ---------------------------------------------------------------------------

  /**
   * Render a small stat pill.
   * @param {string} icon   – emoji icon
   * @param {number} count
   * @param {string} label  – accessible label
   * @param {string} colour – tailwind text-* class
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
        statPill('⬇️', s.downloading, 'Downloading', 'text-primary'),
        statPill('⬆️', s.uploading,   'Uploading',   'text-success'),
        statPill('🌱', s.seeding,     'Seeding',     'text-blue-400'),
        statPill('✅', s.completed,   'Completed',   'text-text-secondary'),
        `<span class="text-text-secondary">/ ${s.total} total</span>`,
      ].join('');
    } catch (_) {
      el.innerHTML = '';
    }
  }

  // ---------------------------------------------------------------------------
  // Boot
  // ---------------------------------------------------------------------------

  function init() {
    // Stagger qB requests slightly so multiple rows do not all hit the API at once.
    setTimeout(function () {
      document.querySelectorAll('[id^="qb-stats-"]').forEach(function (el, index) {
        const serviceId = el.id.replace('qb-stats-', '');
        setTimeout(function () {
          loadQbStats(serviceId);
        }, index * 750);
      });
    }, 3000);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
