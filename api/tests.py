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
