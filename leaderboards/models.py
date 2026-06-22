import re
import secrets
from django.conf import settings
from django.db import models
from django.db.models import F, Q
from django.utils import timezone
from django.utils.text import slugify
from datetime import timedelta


class Leaderboard(models.Model):
    SORT_ORDER_CHOICES = [
        ('desc', 'Highest First'),
        ('asc', 'Lowest First'),
        ('newest', 'Newest First'),
        ('oldest', 'Oldest First'),
    ]

    LEADERBOARD_TYPE_CHOICES = [
        ('score', 'Score'),
        ('correct_answer', 'Correct Answer'),
    ]

    RESET_PERIOD_CHOICES = [
        ('none', 'No reset (lifetime)'),
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
    ]

    game = models.ForeignKey('games.Game', on_delete=models.CASCADE, related_name='leaderboards')
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100)
    description = models.TextField(blank=True)
    api_token = models.CharField(max_length=64, unique=True, editable=False)
    sort_order = models.CharField(max_length=10, choices=SORT_ORDER_CHOICES, default='desc')
    leaderboard_type = models.CharField(
        max_length=20,
        choices=LEADERBOARD_TYPE_CHOICES,
        default='score'
    )
    correct_answer = models.CharField(max_length=64, blank=True, null=True)
    reset_period = models.CharField(
        max_length=10,
        choices=RESET_PERIOD_CHOICES,
        default='none',
        help_text='Reset the leaderboard each day/week. Past periods stay viewable.',
    )
    show_score = models.BooleanField(default=True)
    show_date = models.BooleanField(default=False)
    min_scores_to_keep = models.PositiveIntegerField(default=10)
    max_scores = models.PositiveIntegerField(default=1000)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['game', 'slug']
        ordering = ['name']

    def __str__(self):
        return f"{self.game.name} - {self.name}"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        if not self.api_token:
            self.api_token = secrets.token_urlsafe(32)
        super().save(*args, **kwargs)

    def regenerate_token(self):
        self.api_token = secrets.token_urlsafe(32)
        self.save(update_fields=['api_token'])
        return self.api_token

    def normalize_answer(self, answer):
        """Normalize answer for comparison: lowercase, strip whitespace, remove punctuation."""
        if not answer:
            return ''
        # Convert to lowercase
        normalized = answer.lower()
        # Remove leading/trailing whitespace
        normalized = normalized.strip()
        # Remove all punctuation
        normalized = re.sub(r'[^\w\s]', '', normalized)
        # Collapse multiple whitespace to single space
        normalized = re.sub(r'\s+', ' ', normalized)
        return normalized

    def check_answer(self, submitted_answer):
        """Check if submitted answer matches the correct answer."""
        if self.leaderboard_type != 'correct_answer':
            return True  # Non-puzzle leaderboards always pass
        if not self.correct_answer:
            return True  # No answer configured
        return self.normalize_answer(submitted_answer) == self.normalize_answer(self.correct_answer)

    def clean(self):
        from django.core.exceptions import ValidationError
        super().clean()
        if self.min_scores_to_keep > self.max_scores:
            raise ValidationError({'min_scores_to_keep': 'Cannot exceed max_scores.'})
        if self.min_scores_to_keep > 100:
            raise ValidationError({'min_scores_to_keep': 'Cannot exceed 100.'})
        if self.max_scores > 10000:
            raise ValidationError({'max_scores': 'Cannot exceed 10000.'})
        if self.max_scores < 10:
            raise ValidationError({'max_scores': 'Must be at least 10.'})

    def get_score_ordering(self):
        """Return the field to order scores by (best first)."""
        if self.sort_order == 'asc':
            return 'score'
        elif self.sort_order == 'newest':
            return '-created_at'
        elif self.sort_order == 'oldest':
            return 'created_at'
        else:  # desc
            return '-score'

    def get_period_bounds(self, offset=0):
        """Return (start, end) UTC datetimes for the reset period that is `offset`
        periods before the current one (offset=0 is current, 1 is previous, ...).

        Returns (None, None) for lifetime leaderboards (reset_period == 'none').
        Daily periods run midnight-to-midnight UTC; weekly periods run Monday-to-Monday.
        """
        if self.reset_period == 'none':
            return None, None

        now = timezone.now()
        # Midnight UTC at the start of today.
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        if self.reset_period == 'weekly':
            # Monday is weekday() == 0.
            week_start = day_start - timedelta(days=day_start.weekday())
            start = week_start - timedelta(weeks=offset)
            return start, start + timedelta(weeks=1)

        # daily
        start = day_start - timedelta(days=offset)
        return start, start + timedelta(days=1)

    def get_ordered_scores(self, period_offset=0):
        """Return the visible scores for this leaderboard, filtered and ordered (best first).

        Lifetime boards drop expired scores; period boards return only the requested
        period's scores (period_offset periods back from the current one).
        """
        qs = self.scores.all()
        if self.reset_period == 'none':
            qs = qs.filter(Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now()))
        else:
            start, end = self.get_period_bounds(period_offset)
            qs = qs.filter(created_at__gte=start, created_at__lt=end)
        return qs.order_by(self.get_score_ordering())

    def prune_excess_scores(self, period_offset=0):
        """Remove scores beyond max_scores limit, keeping best based on sort_order.

        For period boards, pruning is scoped to a single period so historical periods
        are never wiped.
        """
        scoped = self.get_ordered_scores(period_offset)
        keep_ids = list(scoped.values_list('id', flat=True)[:self.max_scores])
        if self.reset_period == 'none':
            to_delete = self.scores.exclude(id__in=keep_ids)
        else:
            start, end = self.get_period_bounds(period_offset)
            to_delete = self.scores.filter(
                created_at__gte=start, created_at__lt=end
            ).exclude(id__in=keep_ids)
        return to_delete.delete()


class Score(models.Model):
    leaderboard = models.ForeignKey(Leaderboard, on_delete=models.CASCADE, related_name='scores')
    player_name = models.CharField(max_length=50)
    player_id = models.CharField(max_length=100, null=True)
    score = models.FloatField(null=True, blank=True, default=0)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-score']
        indexes = [
            models.Index(fields=['leaderboard', '-score']),
            models.Index(fields=['expires_at']),
            models.Index(fields=['leaderboard', 'player_id']),
        ]

    def __str__(self):
        return f"{self.player_name}: {self.score}"

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        # Period boards keep scores forever (past periods stay viewable), so they
        # never get a TTL. Lifetime boards expire scores after SCORE_EXPIRATION_DAYS.
        if not self.expires_at and self.leaderboard.reset_period == 'none':
            self.expires_at = timezone.now() + timedelta(days=settings.SCORE_EXPIRATION_DAYS)
        super().save(*args, **kwargs)
        if is_new:
            from games.models import Game
            Game.objects.filter(pk=self.leaderboard.game_id).update(
                total_scores=F('total_scores') + 1
            )

    @classmethod
    def cleanup_expired(cls):
        return cls.objects.filter(expires_at__lt=timezone.now()).delete()
