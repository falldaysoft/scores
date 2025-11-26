from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.views import View
from django.http import HttpResponse

from .models import Game
from .forms import GameForm, GameDeleteConfirmForm
from leaderboards.models import Leaderboard
from leaderboards.forms import LeaderboardForm


class DashboardView(LoginRequiredMixin, View):
    def get(self, request):
        games = request.user.games.prefetch_related('leaderboards')
        return render(request, 'games/dashboard.html', {'games': games})


class GameCreateView(LoginRequiredMixin, View):
    def get(self, request):
        form = GameForm()
        if request.htmx:
            return render(request, 'games/partials/game_form.html', {'form': form})
        return render(request, 'games/game_form.html', {'form': form})

    def post(self, request):
        form = GameForm(request.POST)
        if form.is_valid():
            game = form.save(commit=False)
            game.owner = request.user
            game.save()
            messages.success(request, f'Game "{game.name}" created!')
            if request.htmx:
                return HttpResponse(status=204, headers={'HX-Redirect': f'/dashboard/games/{game.slug}/'})
            return redirect('games:game_detail', slug=game.slug)
        if request.htmx:
            return render(request, 'games/partials/game_form.html', {'form': form})
        return render(request, 'games/game_form.html', {'form': form})


class GameDetailView(LoginRequiredMixin, View):
    def get(self, request, slug):
        game = get_object_or_404(Game, slug=slug, owner=request.user)
        leaderboards = game.leaderboards.all()
        leaderboard_form = LeaderboardForm()
        return render(request, 'games/game_detail.html', {
            'game': game,
            'leaderboards': leaderboards,
            'leaderboard_form': leaderboard_form,
        })


class GameEditView(LoginRequiredMixin, View):
    def get(self, request, slug):
        game = get_object_or_404(Game, slug=slug, owner=request.user)
        form = GameForm(instance=game)
        if request.htmx:
            return render(request, 'games/partials/game_edit_form.html', {'form': form, 'game': game})
        return render(request, 'games/game_form.html', {'form': form, 'game': game})

    def post(self, request, slug):
        game = get_object_or_404(Game, slug=slug, owner=request.user)
        form = GameForm(request.POST, instance=game)
        if form.is_valid():
            form.save()
            messages.success(request, 'Game updated!')
            if request.htmx:
                return HttpResponse(status=204, headers={'HX-Redirect': f'/dashboard/games/{game.slug}/'})
            return redirect('games:game_detail', slug=game.slug)
        if request.htmx:
            return render(request, 'games/partials/game_edit_form.html', {'form': form, 'game': game})
        return render(request, 'games/game_form.html', {'form': form, 'game': game})


class GameDeleteView(LoginRequiredMixin, View):
    def get(self, request, slug):
        game = get_object_or_404(Game, slug=slug, owner=request.user)
        form = GameDeleteConfirmForm(game_name=game.name)
        leaderboard_count = game.leaderboards.count()
        score_count = sum(lb.scores.count() for lb in game.leaderboards.all())
        return render(request, 'games/game_delete_confirm.html', {
            'game': game,
            'form': form,
            'leaderboard_count': leaderboard_count,
            'score_count': score_count,
        })

    def post(self, request, slug):
        game = get_object_or_404(Game, slug=slug, owner=request.user)
        form = GameDeleteConfirmForm(request.POST, game_name=game.name)
        if form.is_valid():
            name = game.name
            game.delete()
            messages.success(request, f'Game "{name}" and all associated data deleted.')
            if request.htmx:
                return HttpResponse(status=204, headers={'HX-Redirect': '/dashboard/'})
            return redirect('games:dashboard')
        leaderboard_count = game.leaderboards.count()
        score_count = sum(lb.scores.count() for lb in game.leaderboards.all())
        return render(request, 'games/game_delete_confirm.html', {
            'game': game,
            'form': form,
            'leaderboard_count': leaderboard_count,
            'score_count': score_count,
        })
