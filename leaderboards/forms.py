from django import forms
from .models import Leaderboard


class LeaderboardForm(forms.ModelForm):
    class Meta:
        model = Leaderboard
        fields = ['name', 'description', 'leaderboard_type', 'correct_answer', 'sort_order', 'show_score', 'show_date',
                  'min_scores_to_keep', 'max_scores']
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
            'leaderboard_type': forms.Select(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent',
                'x-model': 'leaderboardType',
            }),
            'correct_answer': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent',
                'placeholder': 'The correct answer',
            }),
            'sort_order': forms.Select(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent',
            }),
            'show_score': forms.CheckboxInput(attrs={
                'class': 'h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-gray-300 rounded',
            }),
            'show_date': forms.CheckboxInput(attrs={
                'class': 'h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-gray-300 rounded',
            }),
            'min_scores_to_keep': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent',
                'min': 0,
                'max': 100,
            }),
            'max_scores': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent',
                'min': 10,
                'max': 10000,
            }),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        # Only show retention fields to users with can_customize permission
        if not user or not user.can_customize:
            self.fields.pop('min_scores_to_keep', None)
            self.fields.pop('max_scores', None)

    def clean(self):
        cleaned_data = super().clean()
        leaderboard_type = cleaned_data.get('leaderboard_type')
        correct_answer = cleaned_data.get('correct_answer')

        if leaderboard_type == 'correct_answer' and not correct_answer:
            self.add_error('correct_answer', 'Correct answer is required for Correct Answer type leaderboards.')

        # Validate retention policy fields if present
        min_keep = cleaned_data.get('min_scores_to_keep')
        max_scores = cleaned_data.get('max_scores')
        if min_keep is not None and max_scores is not None:
            if min_keep > max_scores:
                self.add_error('min_scores_to_keep', 'Cannot exceed max scores.')

        return cleaned_data
