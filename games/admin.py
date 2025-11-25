from django.contrib import admin
from .models import Game


@admin.register(Game)
class GameAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner', 'slug', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('name', 'owner__email')
    prepopulated_fields = {'slug': ('name',)}
