from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView

from leaderboards.views import PublicGameView, PublicLeaderboardView

urlpatterns = [
    path('backroom/', admin.site.urls),
    path('', TemplateView.as_view(template_name='home.html'), name='home'),
    path('accounts/', include('accounts.urls')),
    path('dashboard/', include('games.urls')),
    path('dashboard/', include('leaderboards.urls')),
    path('api/v1/', include('api.urls')),
    path('play/', include('minigames.urls')),
    # Public leaderboard pages
    path('games/<slug:game_slug>/', PublicGameView.as_view(), name='public_game'),
    path('games/<slug:game_slug>/<slug:leaderboard_slug>/', PublicLeaderboardView.as_view(), name='public_leaderboard'),
]
