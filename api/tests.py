from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient
from accounts.models import User
from games.models import Game
from leaderboards.models import Leaderboard, Score


class ScoreAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        self.game = Game.objects.create(owner=self.user, name='Test Game')
        self.leaderboard = Leaderboard.objects.create(game=self.game, name='High Scores')

    def test_submit_score_success(self):
        response = self.client.post(
            reverse('api:scores'),
            {
                'player_name': 'Player1',
                'score': 1000
            },
            format='json',
            HTTP_AUTHORIZATION=f'Bearer {self.leaderboard.api_token}'
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data['success'])
        self.assertEqual(response.data['message'], 'Score submitted successfully')
        self.assertTrue(Score.objects.filter(player_name='Player1').exists())

    def test_submit_score_with_metadata(self):
        response = self.client.post(
            reverse('api:scores'),
            {
                'player_name': 'Player1',
                'score': 1000,
                'metadata': {'level': 5, 'time': '2:30'}
            },
            format='json',
            HTTP_AUTHORIZATION=f'Bearer {self.leaderboard.api_token}'
        )
        self.assertEqual(response.status_code, 201)
        score = Score.objects.get(player_name='Player1')
        self.assertEqual(score.metadata['level'], 5)

    def test_submit_score_no_token(self):
        response = self.client.post(
            reverse('api:scores'),
            {
                'player_name': 'Player1',
                'score': 1000
            },
            format='json'
        )
        self.assertEqual(response.status_code, 401)
        self.assertFalse(response.data['success'])

    def test_submit_score_invalid_token(self):
        response = self.client.post(
            reverse('api:scores'),
            {
                'player_name': 'Player1',
                'score': 1000
            },
            format='json',
            HTTP_AUTHORIZATION='Bearer invalid-token'
        )
        self.assertEqual(response.status_code, 401)
        self.assertFalse(response.data['success'])

    def test_submit_score_missing_player_name(self):
        response = self.client.post(
            reverse('api:scores'),
            {
                'score': 1000
            },
            format='json',
            HTTP_AUTHORIZATION=f'Bearer {self.leaderboard.api_token}'
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.data['success'])
        self.assertIn('player_name', response.data['error'])

    def test_submit_score_missing_score(self):
        response = self.client.post(
            reverse('api:scores'),
            {
                'player_name': 'Player1'
            },
            format='json',
            HTTP_AUTHORIZATION=f'Bearer {self.leaderboard.api_token}'
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.data['success'])
        self.assertIn('score', response.data['error'])

    def test_submit_score_invalid_score_type(self):
        response = self.client.post(
            reverse('api:scores'),
            {
                'player_name': 'Player1',
                'score': 'not-a-number'
            },
            format='json',
            HTTP_AUTHORIZATION=f'Bearer {self.leaderboard.api_token}'
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.data['success'])

    def test_submit_score_player_name_too_long(self):
        response = self.client.post(
            reverse('api:scores'),
            {
                'player_name': 'A' * 51,
                'score': 1000
            },
            format='json',
            HTTP_AUTHORIZATION=f'Bearer {self.leaderboard.api_token}'
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.data['success'])

    def test_get_scores(self):
        Score.objects.create(leaderboard=self.leaderboard, player_name='Player1', score=1000)
        Score.objects.create(leaderboard=self.leaderboard, player_name='Player2', score=2000)

        response = self.client.get(
            reverse('api:scores'),
            HTTP_AUTHORIZATION=f'Bearer {self.leaderboard.api_token}'
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['scores']), 2)
        # Should be sorted by score descending
        self.assertEqual(response.data['scores'][0]['player_name'], 'Player2')
        self.assertEqual(response.data['scores'][1]['player_name'], 'Player1')

    def test_get_scores_with_limit(self):
        for i in range(10):
            Score.objects.create(leaderboard=self.leaderboard, player_name=f'Player{i}', score=i * 100)

        response = self.client.get(
            reverse('api:scores') + '?limit=5',
            HTTP_AUTHORIZATION=f'Bearer {self.leaderboard.api_token}'
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['scores']), 5)

    def test_submit_score_with_player_id_creates_new(self):
        response = self.client.post(
            reverse('api:scores'),
            {
                'player_name': 'Player1',
                'player_id': 'user-123',
                'score': 1000
            },
            format='json',
            HTTP_AUTHORIZATION=f'Bearer {self.leaderboard.api_token}'
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data['success'])
        self.assertEqual(Score.objects.count(), 1)
        score = Score.objects.first()
        self.assertEqual(score.player_id, 'user-123')
        self.assertEqual(score.score, 1000)

    def test_submit_score_with_player_id_updates_existing(self):
        # First submission
        self.client.post(
            reverse('api:scores'),
            {
                'player_name': 'Player1',
                'player_id': 'user-123',
                'score': 1000
            },
            format='json',
            HTTP_AUTHORIZATION=f'Bearer {self.leaderboard.api_token}'
        )
        self.assertEqual(Score.objects.count(), 1)

        # Second submission with same player_id - should update, not create
        response = self.client.post(
            reverse('api:scores'),
            {
                'player_name': 'Player1 Updated',
                'player_id': 'user-123',
                'score': 2000
            },
            format='json',
            HTTP_AUTHORIZATION=f'Bearer {self.leaderboard.api_token}'
        )
        self.assertEqual(response.status_code, 200)  # 200 for update, not 201
        self.assertTrue(response.data['success'])
        self.assertEqual(Score.objects.count(), 1)  # Still only one score
        score = Score.objects.first()
        self.assertEqual(score.player_name, 'Player1 Updated')
        self.assertEqual(score.score, 2000)

    def test_submit_score_with_player_id_does_not_update_if_worse_desc(self):
        # For desc leaderboards (default), higher score is better
        # First submission with high score
        self.client.post(
            reverse('api:scores'),
            {
                'player_name': 'Player1',
                'player_id': 'user-123',
                'score': 2000
            },
            format='json',
            HTTP_AUTHORIZATION=f'Bearer {self.leaderboard.api_token}'
        )

        # Second submission with lower score - should NOT update
        response = self.client.post(
            reverse('api:scores'),
            {
                'player_name': 'Player1 Updated',
                'player_id': 'user-123',
                'score': 1000
            },
            format='json',
            HTTP_AUTHORIZATION=f'Bearer {self.leaderboard.api_token}'
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['success'])
        self.assertIn('not updated', response.data['message'])
        self.assertFalse(response.data['is_high_score'])
        self.assertEqual(Score.objects.count(), 1)
        score = Score.objects.first()
        self.assertEqual(score.player_name, 'Player1')  # Name not updated
        self.assertEqual(score.score, 2000)  # Score kept original

    def test_submit_score_with_player_id_updates_if_better_asc(self):
        # For asc leaderboards, lower score is better
        self.leaderboard.sort_order = 'asc'
        self.leaderboard.save()

        # First submission with high score
        self.client.post(
            reverse('api:scores'),
            {
                'player_name': 'Player1',
                'player_id': 'user-123',
                'score': 2000
            },
            format='json',
            HTTP_AUTHORIZATION=f'Bearer {self.leaderboard.api_token}'
        )

        # Second submission with lower score - should update
        response = self.client.post(
            reverse('api:scores'),
            {
                'player_name': 'Player1 Updated',
                'player_id': 'user-123',
                'score': 1000
            },
            format='json',
            HTTP_AUTHORIZATION=f'Bearer {self.leaderboard.api_token}'
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['success'])
        self.assertIn('updated', response.data['message'])
        self.assertTrue(response.data['is_high_score'])
        score = Score.objects.first()
        self.assertEqual(score.player_name, 'Player1 Updated')
        self.assertEqual(score.score, 1000)

    def test_submit_score_with_player_id_does_not_update_if_worse_asc(self):
        # For asc leaderboards, lower score is better
        self.leaderboard.sort_order = 'asc'
        self.leaderboard.save()

        # First submission with low score
        self.client.post(
            reverse('api:scores'),
            {
                'player_name': 'Player1',
                'player_id': 'user-123',
                'score': 1000
            },
            format='json',
            HTTP_AUTHORIZATION=f'Bearer {self.leaderboard.api_token}'
        )

        # Second submission with higher score - should NOT update
        response = self.client.post(
            reverse('api:scores'),
            {
                'player_name': 'Player1 Updated',
                'player_id': 'user-123',
                'score': 2000
            },
            format='json',
            HTTP_AUTHORIZATION=f'Bearer {self.leaderboard.api_token}'
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['success'])
        self.assertIn('not updated', response.data['message'])
        self.assertFalse(response.data['is_high_score'])
        score = Score.objects.first()
        self.assertEqual(score.player_name, 'Player1')  # Name not updated
        self.assertEqual(score.score, 1000)  # Score kept original

    def test_submit_score_without_player_id_always_creates(self):
        # Two submissions without player_id should create two scores
        self.client.post(
            reverse('api:scores'),
            {'player_name': 'Player1', 'score': 1000},
            format='json',
            HTTP_AUTHORIZATION=f'Bearer {self.leaderboard.api_token}'
        )
        self.client.post(
            reverse('api:scores'),
            {'player_name': 'Player1', 'score': 2000},
            format='json',
            HTTP_AUTHORIZATION=f'Bearer {self.leaderboard.api_token}'
        )
        self.assertEqual(Score.objects.count(), 2)

    def test_submit_score_empty_player_id_treated_as_none(self):
        # Empty string player_id should be treated as no player_id
        self.client.post(
            reverse('api:scores'),
            {'player_name': 'Player1', 'player_id': '', 'score': 1000},
            format='json',
            HTTP_AUTHORIZATION=f'Bearer {self.leaderboard.api_token}'
        )
        self.client.post(
            reverse('api:scores'),
            {'player_name': 'Player1', 'player_id': '   ', 'score': 2000},
            format='json',
            HTTP_AUTHORIZATION=f'Bearer {self.leaderboard.api_token}'
        )
        # Both should create new scores since empty/whitespace player_id is treated as None
        self.assertEqual(Score.objects.count(), 2)

    def test_player_id_scoped_to_leaderboard(self):
        # Same player_id on different leaderboards should create separate scores
        other_leaderboard = Leaderboard.objects.create(game=self.game, name='Other Board')

        self.client.post(
            reverse('api:scores'),
            {'player_name': 'Player1', 'player_id': 'user-123', 'score': 1000},
            format='json',
            HTTP_AUTHORIZATION=f'Bearer {self.leaderboard.api_token}'
        )
        self.client.post(
            reverse('api:scores'),
            {'player_name': 'Player1', 'player_id': 'user-123', 'score': 2000},
            format='json',
            HTTP_AUTHORIZATION=f'Bearer {other_leaderboard.api_token}'
        )
        self.assertEqual(Score.objects.count(), 2)

    def test_player_id_not_in_get_response(self):
        Score.objects.create(
            leaderboard=self.leaderboard,
            player_name='Player1',
            player_id='secret-id-123',
            score=1000
        )
        response = self.client.get(
            reverse('api:scores'),
            HTTP_AUTHORIZATION=f'Bearer {self.leaderboard.api_token}'
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('player_id', response.data['scores'][0])

    def test_submit_integer_score(self):
        """Test submitting an integer score (e.g., points in arcade game)"""
        response = self.client.post(
            reverse('api:scores'),
            {
                'player_name': 'Player1',
                'score': 5000
            },
            format='json',
            HTTP_AUTHORIZATION=f'Bearer {self.leaderboard.api_token}'
        )
        self.assertEqual(response.status_code, 201)
        score = Score.objects.get(player_name='Player1')
        self.assertEqual(score.score, 5000)

    def test_submit_float_score(self):
        """Test submitting a float score (e.g., time in seconds)"""
        response = self.client.post(
            reverse('api:scores'),
            {
                'player_name': 'Player1',
                'score': 84.21
            },
            format='json',
            HTTP_AUTHORIZATION=f'Bearer {self.leaderboard.api_token}'
        )
        self.assertEqual(response.status_code, 201)
        score = Score.objects.get(player_name='Player1')
        self.assertAlmostEqual(score.score, 84.21, places=2)

    def test_submit_float_score_precision(self):
        """Test that float scores maintain reasonable precision"""
        response = self.client.post(
            reverse('api:scores'),
            {
                'player_name': 'Player1',
                'score': 12.3456789
            },
            format='json',
            HTTP_AUTHORIZATION=f'Bearer {self.leaderboard.api_token}'
        )
        self.assertEqual(response.status_code, 201)
        score = Score.objects.get(player_name='Player1')
        # FloatField should preserve several decimal places
        self.assertAlmostEqual(score.score, 12.3456789, places=5)

    def test_get_scores_returns_float_scores(self):
        """Test that GET endpoint returns float scores correctly"""
        Score.objects.create(leaderboard=self.leaderboard, player_name='Player1', score=84.21)
        Score.objects.create(leaderboard=self.leaderboard, player_name='Player2', score=92.55)

        response = self.client.get(
            reverse('api:scores'),
            HTTP_AUTHORIZATION=f'Bearer {self.leaderboard.api_token}'
        )
        self.assertEqual(response.status_code, 200)
        scores = {s['player_name']: s['score'] for s in response.data['scores']}
        self.assertAlmostEqual(scores['Player1'], 84.21, places=2)
        self.assertAlmostEqual(scores['Player2'], 92.55, places=2)

    def test_float_score_comparison_asc_leaderboard(self):
        """Test that float scores are compared correctly on asc leaderboards (lower is better)"""
        self.leaderboard.sort_order = 'asc'
        self.leaderboard.save()

        # First submission: 15.50 seconds
        self.client.post(
            reverse('api:scores'),
            {
                'player_name': 'Player1',
                'player_id': 'user-123',
                'score': 15.50
            },
            format='json',
            HTTP_AUTHORIZATION=f'Bearer {self.leaderboard.api_token}'
        )

        # Second submission: 14.25 seconds (better time, should update)
        response = self.client.post(
            reverse('api:scores'),
            {
                'player_name': 'Player1',
                'player_id': 'user-123',
                'score': 14.25
            },
            format='json',
            HTTP_AUTHORIZATION=f'Bearer {self.leaderboard.api_token}'
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['is_high_score'])
        score = Score.objects.first()
        self.assertAlmostEqual(score.score, 14.25, places=2)

    def test_float_score_comparison_asc_worse_not_updated(self):
        """Test that worse float scores don't update on asc leaderboards"""
        self.leaderboard.sort_order = 'asc'
        self.leaderboard.save()

        # First submission: 14.25 seconds
        self.client.post(
            reverse('api:scores'),
            {
                'player_name': 'Player1',
                'player_id': 'user-123',
                'score': 14.25
            },
            format='json',
            HTTP_AUTHORIZATION=f'Bearer {self.leaderboard.api_token}'
        )

        # Second submission: 15.50 seconds (worse time, should NOT update)
        response = self.client.post(
            reverse('api:scores'),
            {
                'player_name': 'Player1',
                'player_id': 'user-123',
                'score': 15.50
            },
            format='json',
            HTTP_AUTHORIZATION=f'Bearer {self.leaderboard.api_token}'
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data['is_high_score'])
        score = Score.objects.first()
        self.assertAlmostEqual(score.score, 14.25, places=2)

    def test_float_score_comparison_desc_leaderboard(self):
        """Test that float scores are compared correctly on desc leaderboards (higher is better)"""
        # Default is desc
        # First submission: 84.21 points
        self.client.post(
            reverse('api:scores'),
            {
                'player_name': 'Player1',
                'player_id': 'user-123',
                'score': 84.21
            },
            format='json',
            HTTP_AUTHORIZATION=f'Bearer {self.leaderboard.api_token}'
        )

        # Second submission: 92.55 points (better score, should update)
        response = self.client.post(
            reverse('api:scores'),
            {
                'player_name': 'Player1',
                'player_id': 'user-123',
                'score': 92.55
            },
            format='json',
            HTTP_AUTHORIZATION=f'Bearer {self.leaderboard.api_token}'
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['is_high_score'])
        score = Score.objects.first()
        self.assertAlmostEqual(score.score, 92.55, places=2)

    def test_zero_score(self):
        """Test submitting a zero score"""
        response = self.client.post(
            reverse('api:scores'),
            {
                'player_name': 'Player1',
                'score': 0
            },
            format='json',
            HTTP_AUTHORIZATION=f'Bearer {self.leaderboard.api_token}'
        )
        self.assertEqual(response.status_code, 201)
        score = Score.objects.get(player_name='Player1')
        self.assertEqual(score.score, 0)

    def test_negative_score(self):
        """Test submitting a negative score (some games use this)"""
        response = self.client.post(
            reverse('api:scores'),
            {
                'player_name': 'Player1',
                'score': -50
            },
            format='json',
            HTTP_AUTHORIZATION=f'Bearer {self.leaderboard.api_token}'
        )
        self.assertEqual(response.status_code, 201)
        score = Score.objects.get(player_name='Player1')
        self.assertEqual(score.score, -50)


class PublicScoreAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        self.game = Game.objects.create(owner=self.user, name='Test Game')
        self.leaderboard = Leaderboard.objects.create(game=self.game, name='High Scores')

    def test_public_get_scores(self):
        Score.objects.create(leaderboard=self.leaderboard, player_name='Player1', score=1000)

        response = self.client.get(
            reverse('api:public_scores', kwargs={
                'game_slug': self.game.slug,
                'leaderboard_slug': self.leaderboard.slug
            })
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['scores']), 1)
        self.assertEqual(response.data['scores'][0]['player_name'], 'Player1')

    def test_public_get_scores_nonexistent_game(self):
        response = self.client.get(
            reverse('api:public_scores', kwargs={
                'game_slug': 'nonexistent',
                'leaderboard_slug': self.leaderboard.slug
            })
        )
        self.assertEqual(response.status_code, 404)

    def test_public_get_scores_nonexistent_leaderboard(self):
        response = self.client.get(
            reverse('api:public_scores', kwargs={
                'game_slug': self.game.slug,
                'leaderboard_slug': 'nonexistent'
            })
        )
        self.assertEqual(response.status_code, 404)

    def test_public_player_id_not_exposed(self):
        Score.objects.create(
            leaderboard=self.leaderboard,
            player_name='Player1',
            player_id='secret-id-123',
            score=1000
        )
        response = self.client.get(
            reverse('api:public_scores', kwargs={
                'game_slug': self.game.slug,
                'leaderboard_slug': self.leaderboard.slug
            })
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('player_id', response.data['scores'][0])


class DailyLeaderboardAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(email='daily@example.com', password='testpass123')
        self.game = Game.objects.create(owner=self.user, name='Daily Game')
        self.board = Leaderboard.objects.create(
            game=self.game, name='Daily Board', reset_period='daily'
        )

    def _post(self, **data):
        return self.client.post(
            reverse('api:scores'), data, format='json',
            HTTP_AUTHORIZATION=f'Bearer {self.board.api_token}'
        )

    def _backdate(self, score, days):
        # created_at is auto_now_add, so move it into a prior period directly.
        Score.objects.filter(pk=score.pk).update(
            created_at=timezone.now() - timedelta(days=days)
        )

    def test_period_board_score_never_expires(self):
        self._post(player_name='P1', score=100)
        self.assertIsNone(Score.objects.get().expires_at)

    def test_same_day_same_player_keeps_best(self):
        self._post(player_name='P1', player_id='u1', score=100)
        resp = self._post(player_name='P1', player_id='u1', score=250)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Score.objects.count(), 1)
        self.assertEqual(Score.objects.get().score, 250)

    def test_new_day_creates_fresh_entry(self):
        self._post(player_name='P1', player_id='u1', score=100)
        self._backdate(Score.objects.get(), days=1)
        # Same player, new day -> a second row, yesterday's untouched.
        resp = self._post(player_name='P1', player_id='u1', score=50)
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(Score.objects.count(), 2)

    def test_get_default_returns_only_current_period(self):
        self._post(player_name='Today', score=100)
        old = self._post(player_name='Yesterday', score=999)
        self._backdate(Score.objects.get(player_name='Yesterday'), days=1)

        resp = self.client.get(
            reverse('api:scores'), HTTP_AUTHORIZATION=f'Bearer {self.board.api_token}'
        )
        names = [s['player_name'] for s in resp.data['scores']]
        self.assertEqual(names, ['Today'])
        self.assertEqual(resp.data['leaderboard']['reset_period'], 'daily')
        self.assertEqual(resp.data['leaderboard']['period_offset'], 0)
        self.assertIsNotNone(resp.data['leaderboard']['period_start'])

    def test_get_previous_period(self):
        self._post(player_name='Today', score=100)
        self._post(player_name='Yesterday', score=999)
        self._backdate(Score.objects.get(player_name='Yesterday'), days=1)

        resp = self.client.get(
            reverse('api:scores') + '?period=1',
            HTTP_AUTHORIZATION=f'Bearer {self.board.api_token}'
        )
        names = [s['player_name'] for s in resp.data['scores']]
        self.assertEqual(names, ['Yesterday'])

    def test_public_get_previous_period(self):
        self._post(player_name='Today', score=100)
        self._post(player_name='Yesterday', score=999)
        self._backdate(Score.objects.get(player_name='Yesterday'), days=1)

        url = reverse('api:public_scores', kwargs={
            'game_slug': self.game.slug, 'leaderboard_slug': self.board.slug
        })
        resp = self.client.get(url + '?period=1')
        names = [s['player_name'] for s in resp.data['scores']]
        self.assertEqual(names, ['Yesterday'])


class CorrectAnswerLeaderboardTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        self.game = Game.objects.create(owner=self.user, name='Puzzle Game')
        self.puzzle_leaderboard = Leaderboard.objects.create(
            game=self.game,
            name='Puzzle Board',
            leaderboard_type='correct_answer',
            correct_answer='The Answer'
        )

    def test_submit_correct_answer_without_score(self):
        """Test submitting correct answer without score defaults to 0"""
        response = self.client.post(
            reverse('api:scores'),
            {'player_name': 'Player1', 'answer': 'the answer'},
            format='json',
            HTTP_AUTHORIZATION=f'Bearer {self.puzzle_leaderboard.api_token}'
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data['success'])
        self.assertEqual(Score.objects.count(), 1)
        self.assertEqual(Score.objects.first().score, 0)

    def test_submit_correct_answer_with_score(self):
        """Test submitting correct answer with optional time score"""
        response = self.client.post(
            reverse('api:scores'),
            {'player_name': 'Player1', 'answer': 'the answer', 'score': 5000},
            format='json',
            HTTP_AUTHORIZATION=f'Bearer {self.puzzle_leaderboard.api_token}'
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data['success'])
        self.assertEqual(Score.objects.first().score, 5000)

    def test_submit_wrong_answer(self):
        """Test that wrong answer returns 400 error"""
        response = self.client.post(
            reverse('api:scores'),
            {'player_name': 'Player1', 'answer': 'wrong answer'},
            format='json',
            HTTP_AUTHORIZATION=f'Bearer {self.puzzle_leaderboard.api_token}'
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.data['success'])
        self.assertIn('Incorrect answer', response.data['error'])
        self.assertEqual(Score.objects.count(), 0)

    def test_submit_missing_answer(self):
        """Test that missing answer returns 400 error for puzzle leaderboards"""
        response = self.client.post(
            reverse('api:scores'),
            {'player_name': 'Player1'},
            format='json',
            HTTP_AUTHORIZATION=f'Bearer {self.puzzle_leaderboard.api_token}'
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.data['success'])
        self.assertIn('answer is required', response.data['error'])

    def test_answer_case_insensitive(self):
        """Test that answer comparison is case insensitive"""
        response = self.client.post(
            reverse('api:scores'),
            {'player_name': 'Player1', 'answer': 'THE ANSWER'},
            format='json',
            HTTP_AUTHORIZATION=f'Bearer {self.puzzle_leaderboard.api_token}'
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data['success'])

    def test_answer_whitespace_insensitive(self):
        """Test that answer comparison ignores extra whitespace"""
        response = self.client.post(
            reverse('api:scores'),
            {'player_name': 'Player1', 'answer': '  the   answer  '},
            format='json',
            HTTP_AUTHORIZATION=f'Bearer {self.puzzle_leaderboard.api_token}'
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data['success'])

    def test_answer_punctuation_insensitive(self):
        """Test that answer comparison ignores punctuation"""
        response = self.client.post(
            reverse('api:scores'),
            {'player_name': 'Player1', 'answer': 'the answer!'},
            format='json',
            HTTP_AUTHORIZATION=f'Bearer {self.puzzle_leaderboard.api_token}'
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data['success'])

    def test_answer_combined_normalization(self):
        """Test that all normalizations work together"""
        response = self.client.post(
            reverse('api:scores'),
            {'player_name': 'Player1', 'answer': '  THE   ANSWER!!  '},
            format='json',
            HTTP_AUTHORIZATION=f'Bearer {self.puzzle_leaderboard.api_token}'
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data['success'])

    def test_standard_leaderboard_requires_score(self):
        """Test that standard leaderboards still require score"""
        standard_leaderboard = Leaderboard.objects.create(
            game=self.game,
            name='Standard Board',
            leaderboard_type='score'
        )
        response = self.client.post(
            reverse('api:scores'),
            {'player_name': 'Player1'},
            format='json',
            HTTP_AUTHORIZATION=f'Bearer {standard_leaderboard.api_token}'
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.data['success'])
        self.assertIn('score is required', response.data['error'])

    def test_standard_leaderboard_ignores_answer(self):
        """Test that standard leaderboards ignore answer field"""
        standard_leaderboard = Leaderboard.objects.create(
            game=self.game,
            name='Standard Board',
            leaderboard_type='score'
        )
        response = self.client.post(
            reverse('api:scores'),
            {'player_name': 'Player1', 'score': 1000, 'answer': 'anything'},
            format='json',
            HTTP_AUTHORIZATION=f'Bearer {standard_leaderboard.api_token}'
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data['success'])

    def test_get_response_includes_leaderboard_type(self):
        """Test that GET response includes leaderboard type and display settings"""
        Score.objects.create(
            leaderboard=self.puzzle_leaderboard,
            player_name='Player1',
            score=0
        )
        response = self.client.get(
            reverse('api:scores'),
            HTTP_AUTHORIZATION=f'Bearer {self.puzzle_leaderboard.api_token}'
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['leaderboard']['type'], 'correct_answer')
        self.assertIn('show_score', response.data['leaderboard'])
        self.assertIn('show_date', response.data['leaderboard'])
