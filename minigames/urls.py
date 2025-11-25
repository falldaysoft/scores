from django.urls import path
from . import views

app_name = 'minigames'

urlpatterns = [
    path('', views.PlayPageView.as_view(), name='play'),
    path('reaction/', views.ReactionGameView.as_view(), name='reaction'),
    path('memory/', views.MemoryGameView.as_view(), name='memory'),
    path('target/', views.TargetGameView.as_view(), name='target'),
]
