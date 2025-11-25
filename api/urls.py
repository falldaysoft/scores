from django.urls import path
from . import views

app_name = 'api'

urlpatterns = [
    path('scores/', views.ScoreAPIView.as_view(), name='scores'),
    path('scores/<slug:game_slug>/<slug:leaderboard_slug>/', views.PublicScoreAPIView.as_view(), name='public_scores'),
]
