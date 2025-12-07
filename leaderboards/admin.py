from django.contrib import admin
from .models import Leaderboard, Score


@admin.register(Leaderboard)
class LeaderboardAdmin(admin.ModelAdmin):
    list_display = ('name', 'game', 'slug', 'min_scores_to_keep', 'max_scores', 'created_at')
    list_filter = ('game', 'created_at')
    search_fields = ('name', 'game__name')
    fieldsets = (
        (None, {'fields': ('game', 'name', 'slug', 'description')}),
        ('Type & Sorting', {'fields': ('leaderboard_type', 'correct_answer', 'sort_order')}),
        ('Display', {'fields': ('show_score', 'show_date')}),
        ('Retention Policy', {'fields': ('min_scores_to_keep', 'max_scores')}),
    )


@admin.register(Score)
class ScoreAdmin(admin.ModelAdmin):
    list_display = ('player_name', 'score', 'leaderboard', 'created_at', 'expires_at')
    list_filter = ('leaderboard', 'created_at')
    search_fields = ('player_name',)
