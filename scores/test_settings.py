from .settings import *

# Use an in-memory SQLite database for tests
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

# Speed up password hashing for tests
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.MD5PasswordHasher',
]

# Disable email sending in tests
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
