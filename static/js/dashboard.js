// Dashboard JavaScript

// CSRF Token helper
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

const csrftoken = getCookie('csrftoken');
const SERVICE_HEALTH_POLL_SECONDS = 30;
const INITIAL_SERVICE_HEALTH_DELAY_SECONDS = 10;

const STATUS_STYLES = {
    up: {
        row: 'border-l-success',
        badge: 'bg-success/15 text-success border border-success/30',
        dot: 'bg-success',
    },
    down: {
        row: 'border-l-danger',
        badge: 'bg-danger/15 text-danger border border-danger/30',
        dot: 'bg-danger',
    },
    unknown: {
        row: 'border-l-warning',
        badge: 'bg-warning/15 text-warning border border-warning/30',
        dot: 'bg-warning',
    },
};

function getRefreshButtons() {
    return Array.from(document.querySelectorAll('#refresh-btn, #refresh-services-btn'));
}

// Open service in new tab
function openService(url) {
    window.open(url, '_blank');
}

// Refresh services
async function refreshServices() {
    const loadingOverlay = document.getElementById('loading-overlay');
    const refreshButtons = getRefreshButtons();
    
    try {
        // Show loading
        if (loadingOverlay) loadingOverlay.style.display = 'flex';
        refreshButtons.forEach(button => {
            button.disabled = true;
        });
        
        // Call refresh API
        const response = await fetch('/api/services/refresh/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrftoken,
            },
        });
        
        const data = await response.json();
        
        if (data.success) {
            // Show info message if in manual mode or Traefik unavailable
            if (data.info) {
                console.log('ℹ️ ' + data.info);
                // Only show alert if no services were synced and user might be expecting Traefik
                if (data.synced_services === 0 && data.traefik_configured) {
                    alert('ℹ️ ' + data.info);
                }
            }
            
            // Reload page to show updated services
            window.location.reload();
        } else {
            alert('Error refreshing services: ' + data.error);
        }
    } catch (error) {
        console.error('Error refreshing services:', error);
        alert('Failed to refresh services. Please try again.');
    } finally {
        if (loadingOverlay) loadingOverlay.style.display = 'none';
        refreshButtons.forEach(button => {
            button.disabled = false;
        });
    }
}

// Auto-refresh services periodically
let autoRefreshInterval = null;
let healthCheckInterval = null;
let healthCheckInFlight = false;

function startAutoRefresh(intervalSeconds = 300) {
    // Clear existing interval
    if (autoRefreshInterval) {
        clearInterval(autoRefreshInterval);
    }
    
    // Set new interval (default 5 minutes)
    autoRefreshInterval = setInterval(async () => {
        console.log('Auto-refreshing services...');
        await fetchServicesData();
    }, intervalSeconds * 1000);
}

// Check live health without Traefik sync or page reload
async function checkServicesHealth() {
    if (healthCheckInFlight) return;
    healthCheckInFlight = true;

    try {
        const response = await fetch('/api/services/health/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrftoken,
            },
        });
        const data = await response.json();

        if (data.success) {
            updateStats(data);
            updateServiceCards(data.services);

            const lastUpdated = document.getElementById('last-updated');
            if (lastUpdated) {
                lastUpdated.textContent = new Date(data.timestamp).toLocaleString();
            }
        }
    } catch (error) {
        console.error('Error checking services health:', error);
    } finally {
        healthCheckInFlight = false;
    }
}

function startServiceHealthPolling(intervalSeconds = SERVICE_HEALTH_POLL_SECONDS) {
    if (healthCheckInterval) {
        clearInterval(healthCheckInterval);
    }

    setTimeout(checkServicesHealth, INITIAL_SERVICE_HEALTH_DELAY_SECONDS * 1000);
    healthCheckInterval = setInterval(checkServicesHealth, intervalSeconds * 1000);
}

// Fetch services data without page reload
async function fetchServicesData() {
    try {
        const response = await fetch('/api/services/');
        const data = await response.json();
        
        // Update stats
        updateStats(data);
        
        // Update service cards
        updateServiceCards(data.services);
        
        // Update last updated time
        const lastUpdated = document.getElementById('last-updated');
        if (lastUpdated) {
            lastUpdated.textContent = new Date(data.timestamp).toLocaleString();
        }
    } catch (error) {
        console.error('Error fetching services:', error);
    }
}

// Update statistics
function updateStats(data) {
    const totalServices = document.getElementById('total-services');
    const upServices = document.getElementById('up-services');
    const downServices = document.getElementById('down-services');
    
    if (totalServices) totalServices.textContent = data.total;
    
    const upCount = data.services.filter(s => s.status === 'up').length;
    const downCount = data.services.filter(s => s.status === 'down').length;
    
    if (upServices) upServices.textContent = upCount;
    if (downServices) downServices.textContent = downCount;
}

// Update service cards in the grid
function updateServiceCards(services) {
    services.forEach(service => {
        const card = document.querySelector(`[data-service-id="${service.id}"]`);
        if (!card) return;

        const status = STATUS_STYLES[service.status] ? service.status : 'unknown';
        const styles = STATUS_STYLES[status];

        // Update status badge
        const statusBadge = card.querySelector('[data-status-badge]');
        if (statusBadge) {
            statusBadge.className = `flex items-center gap-1 px-2.5 py-1 rounded-full text-[11px] font-bold uppercase tracking-wider ${styles.badge}`;

            const statusDot = statusBadge.querySelector('[data-status-dot]');
            if (statusDot) {
                statusDot.className = `w-1.5 h-1.5 rounded-full ${styles.dot}`;
            }

            Array.from(statusBadge.childNodes).forEach(node => {
                if (node.nodeType === Node.TEXT_NODE) node.remove();
            });
            statusBadge.appendChild(document.createTextNode(status.toUpperCase()));
        }

        // Update row border color
        card.classList.remove('border-l-success', 'border-l-danger', 'border-l-warning');
        card.classList.add(styles.row);

        // Update response time if available
        const responseTimeEl = card.querySelector('[data-response-time]');
        if (responseTimeEl) {
            const responseTimeValue = responseTimeEl.querySelector('span');
            if (service.response_time) {
                if (responseTimeValue) responseTimeValue.textContent = service.response_time;
                responseTimeEl.classList.remove('hidden');
            } else {
                if (responseTimeValue) responseTimeValue.textContent = '';
                responseTimeEl.classList.add('hidden');
            }
        }
    });
}

// Initialize
document.addEventListener('DOMContentLoaded', function() {
    // Attach refresh button event
    getRefreshButtons().forEach(button => {
        button.addEventListener('click', refreshServices);
    });
    
    // Add Service Modal
    const addServiceBtn = document.getElementById('add-service-btn');
    const addServiceModal = document.getElementById('add-service-modal');
    const closeModalBtn = document.getElementById('close-modal-btn');
    const cancelModalBtn = document.getElementById('cancel-modal-btn');
    const addServiceForm = document.getElementById('add-service-form');
    
    if (addServiceBtn && addServiceModal) {
        addServiceBtn.addEventListener('click', () => {
            addServiceModal.style.display = 'flex';
            document.getElementById('service-name').focus();
        });
    }
    
    if (closeModalBtn && addServiceModal) {
        closeModalBtn.addEventListener('click', () => {
            addServiceModal.style.display = 'none';
            addServiceForm.reset();
            document.getElementById('form-error').classList.add('hidden');
        });
    }
    
    if (cancelModalBtn && addServiceModal) {
        cancelModalBtn.addEventListener('click', () => {
            addServiceModal.style.display = 'none';
            addServiceForm.reset();
            document.getElementById('form-error').classList.add('hidden');
        });
    }
    
    // Close modal on outside click
    if (addServiceModal) {
        addServiceModal.addEventListener('click', (e) => {
            if (e.target === addServiceModal) {
                addServiceModal.style.display = 'none';
                addServiceForm.reset();
                document.getElementById('form-error').classList.add('hidden');
            }
        });
    }
    
    // Handle form submission
    if (addServiceForm) {
        addServiceForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const formError = document.getElementById('form-error');
            formError.classList.add('hidden');
            
            const formData = {
                name: document.getElementById('service-name').value.trim(),
                url: document.getElementById('service-url').value.trim(),
                description: document.getElementById('service-description').value.trim(),
                icon: document.getElementById('service-icon').value.trim(),
                service_type: document.getElementById('service-type').value,
                provider: document.getElementById('service-provider').value,
                tags: document.getElementById('service-tags').value.trim(),
            };
            
            try {
                const response = await fetch('/api/services/create/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': csrftoken,
                    },
                    body: JSON.stringify(formData),
                });
                
                const data = await response.json();
                
                if (data.success) {
                    // Close modal and reload page
                    addServiceModal.style.display = 'none';
                    addServiceForm.reset();
                    window.location.reload();
                } else {
                    formError.textContent = data.error || 'Failed to create service';
                    formError.classList.remove('hidden');
                }
            } catch (error) {
                console.error('Error creating service:', error);
                formError.textContent = 'Network error. Please try again.';
                formError.classList.remove('hidden');
            }
        });
    }
    
    // Refresh stored data shortly after load without triggering health checks.
    setTimeout(async () => {
        await fetchServicesData();
    }, 2000);

    startServiceHealthPolling();

    document.addEventListener('visibilitychange', () => {
        if (!document.hidden) {
            checkServicesHealth();
        }
    });
    
    // Start auto-refresh (every 5 minutes)
    // Uncomment to enable auto-refresh
    // startAutoRefresh(300);
    
    console.log('HomeLab Dashboard initialized');
});

// Keyboard shortcuts
document.addEventListener('keydown', function(e) {
    // Press 'R' to refresh (but not when typing in input fields)
    if (e.key === 'r' || e.key === 'R') {
        // Check if user is typing in an input/textarea/select element
        const activeElement = document.activeElement;
        const isTyping = activeElement && (
            activeElement.tagName === 'INPUT' ||
            activeElement.tagName === 'TEXTAREA' ||
            activeElement.tagName === 'SELECT' ||
            activeElement.isContentEditable
        );
        
        // Only trigger refresh if not typing and no modifier keys
        if (!isTyping && !e.ctrlKey && !e.metaKey && !e.altKey) {
            e.preventDefault();
            refreshServices();
        }
    }
});
