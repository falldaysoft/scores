from django.urls import path
from . import views

app_name = 'leaderboards'

urlpatterns = [
    # Dashboard URLs
    path('games/<slug:game_slug>/leaderboards/new/', views.LeaderboardCreateView.as_view(), name='leaderboard_create'),
    path('games/<slug:game_slug>/leaderboards/<slug:leaderboard_slug>/', views.LeaderboardDetailView.as_view(), name='leaderboard_detail'),
    path('games/<slug:game_slug>/leaderboards/<slug:leaderboard_slug>/edit/', views.LeaderboardEditView.as_view(), name='leaderboard_edit'),
    path('games/<slug:game_slug>/leaderboards/<slug:leaderboard_slug>/delete/', views.LeaderboardDeleteView.as_view(), name='leaderboard_delete'),
    path('games/<slug:game_slug>/leaderboards/<slug:leaderboard_slug>/regenerate-token/', views.RegenerateTokenView.as_view(), name='regenerate_token'),
]

# Public URLs are defined in the main urls.py
