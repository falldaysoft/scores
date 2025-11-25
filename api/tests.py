from django.test import TestCase
from django.urls import reverse
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
        self.assertEqual(response.data['player_name'], 'Player1')
        self.assertEqual(response.data['score'], 1000)
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
