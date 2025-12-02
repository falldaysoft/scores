import re
import secrets
from django.conf import settings
from django.db import models
from django.db.models import F
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
    show_score = models.BooleanField(default=True)
    show_date = models.BooleanField(default=False)
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


class Score(models.Model):
    leaderboard = models.ForeignKey(Leaderboard, on_delete=models.CASCADE, related_name='scores')
    player_name = models.CharField(max_length=50)
    player_id = models.CharField(max_length=100, null=True)
    score = models.BigIntegerField(null=True, blank=True, default=0)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField()

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
        if not self.expires_at:
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
