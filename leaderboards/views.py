from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.views import View
from django.http import HttpResponse
from django.utils import timezone

from games.models import Game
from .models import Leaderboard, Score
from .forms import LeaderboardForm


class LeaderboardCreateView(LoginRequiredMixin, View):
    def post(self, request, game_slug):
        game = get_object_or_404(Game, slug=game_slug, owner=request.user)
        form = LeaderboardForm(request.POST)
        if form.is_valid():
            leaderboard = form.save(commit=False)
            leaderboard.game = game
            leaderboard.save()
            messages.success(request, f'Leaderboard "{leaderboard.name}" created!')
            if request.htmx:
                return HttpResponse(status=204, headers={'HX-Redirect': f'/dashboard/games/{game.slug}/'})
        return redirect('games:game_detail', slug=game.slug)


class LeaderboardDetailView(LoginRequiredMixin, View):
    def get(self, request, game_slug, leaderboard_slug):
        game = get_object_or_404(Game, slug=game_slug, owner=request.user)
        leaderboard = get_object_or_404(Leaderboard, slug=leaderboard_slug, game=game)
        scores = leaderboard.scores.filter(expires_at__gt=timezone.now())
        if leaderboard.sort_order == 'asc':
            scores = scores.order_by('score')
        elif leaderboard.sort_order == 'newest':
            scores = scores.order_by('-created_at')
        elif leaderboard.sort_order == 'oldest':
            scores = scores.order_by('created_at')
        else:
            scores = scores.order_by('-score')
        return render(request, 'leaderboards/leaderboard_detail.html', {
            'game': game,
            'leaderboard': leaderboard,
            'scores': scores[:100],
        })


class LeaderboardEditView(LoginRequiredMixin, View):
    def get(self, request, game_slug, leaderboard_slug):
        game = get_object_or_404(Game, slug=game_slug, owner=request.user)
        leaderboard = get_object_or_404(Leaderboard, slug=leaderboard_slug, game=game)
        form = LeaderboardForm(instance=leaderboard)
        if request.htmx:
            return render(request, 'leaderboards/partials/leaderboard_edit_form.html', {
                'form': form, 'game': game, 'leaderboard': leaderboard
            })
        return render(request, 'leaderboards/leaderboard_form.html', {
            'form': form, 'game': game, 'leaderboard': leaderboard
        })

    def post(self, request, game_slug, leaderboard_slug):
        game = get_object_or_404(Game, slug=game_slug, owner=request.user)
        leaderboard = get_object_or_404(Leaderboard, slug=leaderboard_slug, game=game)
        form = LeaderboardForm(request.POST, instance=leaderboard)
        if form.is_valid():
            form.save()
            messages.success(request, 'Leaderboard updated!')
            if request.htmx:
                return HttpResponse(status=204, headers={
                    'HX-Redirect': f'/dashboard/games/{game.slug}/leaderboards/{leaderboard.slug}/'
                })
            return redirect('leaderboards:leaderboard_detail', game_slug=game.slug, leaderboard_slug=leaderboard.slug)
        if request.htmx:
            return render(request, 'leaderboards/partials/leaderboard_edit_form.html', {
                'form': form, 'game': game, 'leaderboard': leaderboard
            })
        return render(request, 'leaderboards/leaderboard_form.html', {
            'form': form, 'game': game, 'leaderboard': leaderboard
        })


class LeaderboardDeleteView(LoginRequiredMixin, View):
    def post(self, request, game_slug, leaderboard_slug):
        game = get_object_or_404(Game, slug=game_slug, owner=request.user)
        leaderboard = get_object_or_404(Leaderboard, slug=leaderboard_slug, game=game)
        name = leaderboard.name
        leaderboard.delete()
        messages.success(request, f'Leaderboard "{name}" deleted.')
        if request.htmx:
            return HttpResponse(status=204, headers={'HX-Redirect': f'/dashboard/games/{game.slug}/'})
        return redirect('games:game_detail', slug=game.slug)


class LeaderboardResetScoresView(LoginRequiredMixin, View):
    def post(self, request, game_slug, leaderboard_slug):
        game = get_object_or_404(Game, slug=game_slug, owner=request.user)
        leaderboard = get_object_or_404(Leaderboard, slug=leaderboard_slug, game=game)
        deleted_count, _ = leaderboard.scores.all().delete()
        messages.success(request, f'Deleted {deleted_count} score(s) from "{leaderboard.name}".')
        if request.htmx:
            return HttpResponse(status=204, headers={
                'HX-Redirect': f'/dashboard/games/{game.slug}/leaderboards/{leaderboard.slug}/'
            })
        return redirect('leaderboards:leaderboard_detail', game_slug=game.slug, leaderboard_slug=leaderboard.slug)


class RegenerateTokenView(LoginRequiredMixin, View):
    def post(self, request, game_slug, leaderboard_slug):
        game = get_object_or_404(Game, slug=game_slug, owner=request.user)
        leaderboard = get_object_or_404(Leaderboard, slug=leaderboard_slug, game=game)
        leaderboard.regenerate_token()
        messages.success(request, 'API token regenerated!')
        if request.htmx:
            return render(request, 'leaderboards/partials/api_token.html', {'leaderboard': leaderboard})
        return redirect('leaderboards:leaderboard_detail', game_slug=game.slug, leaderboard_slug=leaderboard.slug)


# Public views
class PublicGameView(View):
    def get(self, request, game_slug):
        game = get_object_or_404(Game, slug=game_slug)
        leaderboards = game.leaderboards.all()
        return render(request, 'leaderboards/public_game.html', {
            'game': game,
            'leaderboards': leaderboards,
        })


class PublicLeaderboardView(View):
    def get(self, request, game_slug, leaderboard_slug):
        game = get_object_or_404(Game, slug=game_slug)
        leaderboard = get_object_or_404(Leaderboard, slug=leaderboard_slug, game=game)
        scores = leaderboard.scores.filter(expires_at__gt=timezone.now())
        if leaderboard.sort_order == 'asc':
            scores = scores.order_by('score')
        elif leaderboard.sort_order == 'newest':
            scores = scores.order_by('-created_at')
        elif leaderboard.sort_order == 'oldest':
            scores = scores.order_by('created_at')
        else:
            scores = scores.order_by('-score')
        return render(request, 'leaderboards/public_leaderboard.html', {
            'game': game,
            'leaderboard': leaderboard,
            'scores': scores[:100],
        })
