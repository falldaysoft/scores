from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from accounts.models import User
from games.models import Game
from .models import Leaderboard, Score


class LeaderboardModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        self.game = Game.objects.create(owner=self.user, name='Test Game')

    def test_create_leaderboard(self):
        leaderboard = Leaderboard.objects.create(
            game=self.game,
            name='High Scores'
        )
        self.assertEqual(leaderboard.slug, 'high-scores')
        self.assertTrue(len(leaderboard.api_token) > 20)

    def test_regenerate_token(self):
        leaderboard = Leaderboard.objects.create(game=self.game, name='High Scores')
        old_token = leaderboard.api_token
        new_token = leaderboard.regenerate_token()
        self.assertNotEqual(old_token, new_token)
        self.assertEqual(leaderboard.api_token, new_token)


class ScoreModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        self.game = Game.objects.create(owner=self.user, name='Test Game')
        self.leaderboard = Leaderboard.objects.create(game=self.game, name='High Scores')

    def test_create_score(self):
        score = Score.objects.create(
            leaderboard=self.leaderboard,
            player_name='Player1',
            score=1000
        )
        self.assertEqual(str(score), 'Player1: 1000')
        self.assertIsNotNone(score.expires_at)

    def test_score_expiration(self):
        score = Score.objects.create(
            leaderboard=self.leaderboard,
            player_name='Player1',
            score=1000
        )
        # Score should expire in ~7 days
        expected_expiry = timezone.now() + timedelta(days=7)
        self.assertAlmostEqual(
            score.expires_at.timestamp(),
            expected_expiry.timestamp(),
            delta=60  # Within 60 seconds
        )

    def test_cleanup_expired_scores(self):
        # Create expired score
        expired_score = Score.objects.create(
            leaderboard=self.leaderboard,
            player_name='Expired',
            score=500
        )
        expired_score.expires_at = timezone.now() - timedelta(days=1)
        expired_score.save()

        # Create active score
        active_score = Score.objects.create(
            leaderboard=self.leaderboard,
            player_name='Active',
            score=1000
        )

        deleted_count, _ = Score.cleanup_expired()
        self.assertEqual(deleted_count, 1)
        self.assertFalse(Score.objects.filter(pk=expired_score.pk).exists())
        self.assertTrue(Score.objects.filter(pk=active_score.pk).exists())


class LeaderboardViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        self.game = Game.objects.create(owner=self.user, name='Test Game')
        self.leaderboard = Leaderboard.objects.create(game=self.game, name='High Scores')
        self.client.login(username='test@example.com', password='testpass123')

    def test_leaderboard_detail_loads(self):
        response = self.client.get(reverse('leaderboards:leaderboard_detail', kwargs={
            'game_slug': self.game.slug,
            'leaderboard_slug': self.leaderboard.slug
        }))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'High Scores')
        self.assertContains(response, 'API Token')

    def test_leaderboard_shows_scores(self):
        Score.objects.create(leaderboard=self.leaderboard, player_name='Player1', score=1000)
        Score.objects.create(leaderboard=self.leaderboard, player_name='Player2', score=2000)

        response = self.client.get(reverse('leaderboards:leaderboard_detail', kwargs={
            'game_slug': self.game.slug,
            'leaderboard_slug': self.leaderboard.slug
        }))
        self.assertContains(response, 'Player1')
        self.assertContains(response, 'Player2')

    def test_reset_scores_deletes_all_scores(self):
        Score.objects.create(leaderboard=self.leaderboard, player_name='Player1', score=1000)
        Score.objects.create(leaderboard=self.leaderboard, player_name='Player2', score=2000)
        self.assertEqual(Score.objects.filter(leaderboard=self.leaderboard).count(), 2)

        response = self.client.post(reverse('leaderboards:leaderboard_reset_scores', kwargs={
            'game_slug': self.game.slug,
            'leaderboard_slug': self.leaderboard.slug
        }))
        self.assertRedirects(response, reverse('leaderboards:leaderboard_detail', kwargs={
            'game_slug': self.game.slug,
            'leaderboard_slug': self.leaderboard.slug
        }))
        self.assertEqual(Score.objects.filter(leaderboard=self.leaderboard).count(), 0)

    def test_reset_scores_requires_auth(self):
        self.client.logout()
        response = self.client.post(reverse('leaderboards:leaderboard_reset_scores', kwargs={
            'game_slug': self.game.slug,
            'leaderboard_slug': self.leaderboard.slug
        }))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)

    def test_reset_scores_requires_ownership(self):
        other_user = User.objects.create_user(email='other@example.com', password='testpass123')
        self.client.login(username='other@example.com', password='testpass123')

        Score.objects.create(leaderboard=self.leaderboard, player_name='Player1', score=1000)

        response = self.client.post(reverse('leaderboards:leaderboard_reset_scores', kwargs={
            'game_slug': self.game.slug,
            'leaderboard_slug': self.leaderboard.slug
        }))
        self.assertEqual(response.status_code, 404)
        self.assertEqual(Score.objects.filter(leaderboard=self.leaderboard).count(), 1)


class PublicLeaderboardViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        self.game = Game.objects.create(owner=self.user, name='Test Game')
        self.leaderboard = Leaderboard.objects.create(game=self.game, name='High Scores')

    def test_public_game_page_loads(self):
        response = self.client.get(reverse('public_game', kwargs={'game_slug': self.game.slug}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Game')

    def test_public_leaderboard_page_loads(self):
        response = self.client.get(reverse('public_leaderboard', kwargs={
            'game_slug': self.game.slug,
            'leaderboard_slug': self.leaderboard.slug
        }))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'High Scores')

    def test_public_leaderboard_shows_scores(self):
        Score.objects.create(leaderboard=self.leaderboard, player_name='TopPlayer', score=5000)

        response = self.client.get(reverse('public_leaderboard', kwargs={
            'game_slug': self.game.slug,
            'leaderboard_slug': self.leaderboard.slug
        }))
        self.assertContains(response, 'TopPlayer')
        self.assertContains(response, '5000')
