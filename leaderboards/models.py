import secrets
from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.text import slugify
from datetime import timedelta


class Leaderboard(models.Model):
    SORT_ORDER_CHOICES = [
        ('desc', 'Highest First'),
        ('asc', 'Lowest First'),
    ]

    game = models.ForeignKey('games.Game', on_delete=models.CASCADE, related_name='leaderboards')
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100)
    description = models.TextField(blank=True)
    api_token = models.CharField(max_length=64, unique=True, editable=False)
    sort_order = models.CharField(max_length=4, choices=SORT_ORDER_CHOICES, default='desc')
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


class Score(models.Model):
    leaderboard = models.ForeignKey(Leaderboard, on_delete=models.CASCADE, related_name='scores')
    player_name = models.CharField(max_length=50)
    score = models.BigIntegerField()
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        ordering = ['-score']
        indexes = [
            models.Index(fields=['leaderboard', '-score']),
            models.Index(fields=['expires_at']),
        ]

    def __str__(self):
        return f"{self.player_name}: {self.score}"

    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(days=settings.SCORE_EXPIRATION_DAYS)
        super().save(*args, **kwargs)

    @classmethod
    def cleanup_expired(cls):
        return cls.objects.filter(expires_at__lt=timezone.now()).delete()
