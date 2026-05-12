"""Settings used by the test suite.

Tests should be runnable on a development machine without PostgreSQL or any
external services. Keep database and cache dependencies local to the process.
"""

from .settings import *

DEBUG = True

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
        'ATOMIC_REQUESTS': False,
    }
}

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'homelab-dashboard-tests',
    }
}
