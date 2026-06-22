from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.shortcuts import get_object_or_404

from leaderboards.models import Leaderboard, Score


def _parse_period(request):
    """Read the ?period=<int> query param (periods back, 0=current). Clamp invalid to 0."""
    try:
        return max(0, int(request.query_params.get('period', 0)))
    except (TypeError, ValueError):
        return 0


def _leaderboard_payload(leaderboard, scores, offset, period_offset):
    """Build the JSON response shared by the authenticated and public GET endpoints."""
    period_start, period_end = leaderboard.get_period_bounds(period_offset)
    return {
        'leaderboard': {
            'name': leaderboard.name,
            'game': leaderboard.game.name,
            'sort_order': leaderboard.sort_order,
            'type': leaderboard.leaderboard_type,
            'show_score': leaderboard.show_score,
            'show_date': leaderboard.show_date,
            'reset_period': leaderboard.reset_period,
            'period_offset': period_offset,
            'period_start': period_start.isoformat() if period_start else None,
            'period_end': period_end.isoformat() if period_end else None,
        },
        'scores': [
            {
                'rank': offset + i + 1,
                'player_name': s.player_name,
                'score': s.score,
                'metadata': s.metadata,
                'created_at': s.created_at.isoformat(),
            }
            for i, s in enumerate(scores)
        ]
    }


class ScoreAPIView(APIView):
    def get_leaderboard(self, request):
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        if not token:
            return None
        return Leaderboard.objects.filter(api_token=token).first()

    def post(self, request):
        """Submit a new score"""
        leaderboard = self.get_leaderboard(request)
        if not leaderboard:
            return Response(
                {'success': False, 'error': 'Invalid or missing API token'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        player_name = request.data.get('player_name', '').strip()
        player_id = request.data.get('player_id')
        if player_id is not None:
            player_id = str(player_id).strip() or None  # Convert empty string to None
        score_value = request.data.get('score')
        metadata = request.data.get('metadata', {})
        answer = request.data.get('answer')

        if not player_name:
            return Response(
                {'success': False, 'error': 'player_name is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if len(player_name) > 50:
            return Response(
                {'success': False, 'error': 'player_name must be 50 characters or less'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Handle correct_answer type leaderboards
        if leaderboard.leaderboard_type == 'correct_answer':
            if not answer:
                return Response(
                    {'success': False, 'error': 'answer is required for this leaderboard'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if not leaderboard.check_answer(answer):
                return Response(
                    {'success': False, 'error': 'Incorrect answer'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            # Score is optional for correct_answer leaderboards
            if score_value is None:
                score_value = 0
        else:
            # Standard leaderboard requires score
            if score_value is None:
                return Response(
                    {'success': False, 'error': 'score is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        try:
            score_value = float(score_value)
        except (ValueError, TypeError):
            return Response(
                {'success': False, 'error': 'score must be a number'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not isinstance(metadata, dict):
            return Response(
                {'success': False, 'error': 'metadata must be an object'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # If player_id provided, update existing score or create new one.
        # For period boards, dedup is scoped to the current period so a returning
        # player gets a fresh entry each day/week instead of updating an old one.
        created = False
        updated = False
        if player_id:
            existing_qs = Score.objects.filter(
                leaderboard=leaderboard,
                player_id=player_id
            )
            if leaderboard.reset_period != 'none':
                start, end = leaderboard.get_period_bounds(0)
                existing_qs = existing_qs.filter(created_at__gte=start, created_at__lt=end)
            existing_score = existing_qs.first()
        else:
            existing_score = None

        if existing_score:
            # Determine if the new score is better based on sort order
            is_better = False
            if leaderboard.sort_order == 'desc':
                # Higher score is better
                is_better = score_value > existing_score.score
            elif leaderboard.sort_order == 'asc':
                # Lower score is better
                is_better = score_value < existing_score.score
            elif leaderboard.sort_order == 'newest':
                # Newer is better, always update
                is_better = True
            elif leaderboard.sort_order == 'oldest':
                # Older is better, never update
                is_better = False

            if is_better:
                existing_score.player_name = player_name
                existing_score.score = score_value
                existing_score.metadata = metadata
                existing_score.expires_at = None  # Will be recalculated on save
                existing_score.save()
                updated = True
                score = existing_score
            else:
                # Keep existing score, don't update
                score = existing_score
        else:
            score = Score.objects.create(
                leaderboard=leaderboard,
                player_name=player_name,
                player_id=player_id,
                score=score_value,
                metadata=metadata
            )
            created = True

        # Prune excess scores if we added a new one
        if created:
            leaderboard.prune_excess_scores()

        if created:
            message = 'Score submitted successfully'
        elif updated:
            message = 'Score updated successfully'
        else:
            message = 'Score not updated (existing score is better)'

        return Response({
            'success': True,
            'message': message,
            'is_high_score': created or updated,
        }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    def get(self, request):
        """Get leaderboard scores"""
        leaderboard = self.get_leaderboard(request)
        if not leaderboard:
            return Response(
                {'error': 'Invalid or missing API token'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        limit = min(int(request.query_params.get('limit', 100)), 100)
        offset = int(request.query_params.get('offset', 0))
        period_offset = _parse_period(request)

        scores = leaderboard.get_ordered_scores(period_offset)[offset:offset + limit]
        return Response(_leaderboard_payload(leaderboard, scores, offset, period_offset))


class PublicScoreAPIView(APIView):
    """Public API to get scores without authentication"""

    def get(self, request, game_slug, leaderboard_slug):
        leaderboard = get_object_or_404(
            Leaderboard,
            slug=leaderboard_slug,
            game__slug=game_slug
        )

        limit = min(int(request.query_params.get('limit', 100)), 100)
        offset = int(request.query_params.get('offset', 0))
        period_offset = _parse_period(request)

        scores = leaderboard.get_ordered_scores(period_offset)[offset:offset + limit]
        return Response(_leaderboard_payload(leaderboard, scores, offset, period_offset))
