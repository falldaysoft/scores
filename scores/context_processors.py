from django.conf import settings


def site_url(request):
    """Add site_url to template context."""
    return {
        'site_url': settings.SITE_URL,
    }
