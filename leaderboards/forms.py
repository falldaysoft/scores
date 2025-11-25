from django import forms
from .models import Leaderboard


class LeaderboardForm(forms.ModelForm):
    class Meta:
        model = Leaderboard
        fields = ['name', 'description', 'sort_order']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent',
                'placeholder': 'e.g., Single Player, Arcade Mode'
            }),
            'description': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent',
                'placeholder': 'Optional description...',
                'rows': 2
            }),
            'sort_order': forms.Select(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent',
            }),
        }
