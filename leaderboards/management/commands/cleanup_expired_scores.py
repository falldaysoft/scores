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
        # Get scores ordered by quality (best first)
        order = leaderboard.get_score_ordering()
        ordered_ids = list(
            leaderboard.scores.order_by(order).values_list('id', flat=True)
        )

        if not ordered_ids:
            return 0

        # Protect top N scores from expiration
        protected_ids = set(ordered_ids[:leaderboard.min_scores_to_keep])

        # Delete expired scores that are NOT protected
        deleted_count, _ = Score.objects.filter(
            leaderboard=leaderboard,
            expires_at__lt=now
        ).exclude(id__in=protected_ids).delete()

        return deleted_count
