from django.core.management.base import BaseCommand
from django.utils import timezone
from leaderboards.models import Leaderboard, Score


class Command(BaseCommand):
    help = 'Remove expired scores from the database, respecting min_scores_to_keep'

    def handle(self, *args, **options):
        total_deleted = 0
        now = timezone.now()

        for leaderboard in Leaderboard.objects.all():
            deleted = self.cleanup_leaderboard(leaderboard, now)
            total_deleted += deleted

        self.stdout.write(
            self.style.SUCCESS(f'Successfully deleted {total_deleted} expired scores')
        )

    def cleanup_leaderboard(self, leaderboard, now):
        """Clean up expired scores for a leaderboard, preserving min_scores_to_keep."""
        # Get the most recent score IDs (newest first)
        recent_ids = list(
            leaderboard.scores.order_by('-created_at')
            .values_list('id', flat=True)[:leaderboard.min_scores_to_keep]
        )

        if not recent_ids:
            return 0

        # Protect the most recent scores from expiration
        protected_ids = set(recent_ids)

        # Delete expired scores that are NOT protected
        deleted_count, _ = Score.objects.filter(
            leaderboard=leaderboard,
            expires_at__lt=now
        ).exclude(id__in=protected_ids).delete()

        return deleted_count
