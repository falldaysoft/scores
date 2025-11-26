from django import forms
from .models import Game


class GameForm(forms.ModelForm):
    class Meta:
        model = Game
        fields = ['name', 'description', 'url']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent',
                'placeholder': 'My Awesome Game'
            }),
            'description': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent',
                'placeholder': 'Brief description of your game...',
                'rows': 3
            }),
            'url': forms.URLInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent',
                'placeholder': 'https://example.com/my-game'
            }),
        }


class GameDeleteConfirmForm(forms.Form):
    confirmation = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-transparent',
            'placeholder': 'Type game name here',
            'autocomplete': 'off',
        })
    )

    def __init__(self, *args, game_name=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.game_name = game_name

    def clean_confirmation(self):
        confirmation = self.cleaned_data.get('confirmation')
        if confirmation != self.game_name:
            raise forms.ValidationError(
                f'Please type "{self.game_name}" exactly to confirm deletion.'
            )
        return confirmation
