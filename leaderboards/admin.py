from django.contrib import admin
from .models import Leaderboard, Score


@admin.register(Leaderboard)
class LeaderboardAdmin(admin.ModelAdmin):
    list_display = ('name', 'game', 'slug', 'created_at')
    list_filter = ('game', 'created_at')
    search_fields = ('name', 'game__name')


@admin.register(Score)
class ScoreAdmin(admin.ModelAdmin):
    list_display = ('player_name', 'score', 'leaderboard', 'created_at', 'expires_at')
    list_filter = ('leaderboard', 'created_at')
    search_fields = ('player_name',)
