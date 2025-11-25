from django.core.management.base import BaseCommand
from leaderboards.models import Score


class Command(BaseCommand):
    help = 'Remove expired scores from the database'

    def handle(self, *args, **options):
        deleted_count, _ = Score.cleanup_expired()
        self.stdout.write(
            self.style.SUCCESS(f'Successfully deleted {deleted_count} expired scores')
        )
