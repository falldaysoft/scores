from django.urls import path
from . import views

app_name = 'games'

urlpatterns = [
    path('', views.DashboardView.as_view(), name='dashboard'),
    path('games/new/', views.GameCreateView.as_view(), name='game_create'),
    path('games/<slug:slug>/', views.GameDetailView.as_view(), name='game_detail'),
    path('games/<slug:slug>/edit/', views.GameEditView.as_view(), name='game_edit'),
    path('games/<slug:slug>/delete/', views.GameDeleteView.as_view(), name='game_delete'),
]
