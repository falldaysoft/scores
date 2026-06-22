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


class ResetPeriodTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='period@example.com', password='testpass123')
        self.game = Game.objects.create(owner=self.user, name='Period Game')

    def test_daily_bounds_are_one_utc_day(self):
        board = Leaderboard.objects.create(game=self.game, name='Daily', reset_period='daily')
        start, end = board.get_period_bounds(0)
        self.assertEqual((start.hour, start.minute, start.second), (0, 0, 0))
        self.assertEqual(end - start, timedelta(days=1))
        # Previous period sits exactly one day earlier.
        prev_start, _ = board.get_period_bounds(1)
        self.assertEqual(start - prev_start, timedelta(days=1))

    def test_weekly_bounds_start_monday(self):
        board = Leaderboard.objects.create(game=self.game, name='Weekly', reset_period='weekly')
        start, end = board.get_period_bounds(0)
        self.assertEqual(start.weekday(), 0)  # Monday
        self.assertEqual((start.hour, start.minute, start.second), (0, 0, 0))
        self.assertEqual(end - start, timedelta(weeks=1))

    def test_lifetime_bounds_are_none(self):
        board = Leaderboard.objects.create(game=self.game, name='Lifetime', reset_period='none')
        self.assertEqual(board.get_period_bounds(0), (None, None))

    def test_period_score_has_no_expiry_and_survives_cleanup(self):
        board = Leaderboard.objects.create(game=self.game, name='Daily', reset_period='daily')
        score = Score.objects.create(leaderboard=board, player_name='P1', score=100)
        self.assertIsNone(score.expires_at)
        deleted_count, _ = Score.cleanup_expired()
        self.assertEqual(deleted_count, 0)
        self.assertTrue(Score.objects.filter(pk=score.pk).exists())

    def test_get_ordered_scores_filters_to_current_period(self):
        board = Leaderboard.objects.create(game=self.game, name='Daily', reset_period='daily')
        today = Score.objects.create(leaderboard=board, player_name='Today', score=100)
        old = Score.objects.create(leaderboard=board, player_name='Old', score=100)
        Score.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(days=1))

        current = list(board.get_ordered_scores())
        self.assertEqual(current, [today])
        previous = list(board.get_ordered_scores(period_offset=1))
        self.assertEqual([s.pk for s in previous], [old.pk])


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


class LeaderboardCreateViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        self.game = Game.objects.create(owner=self.user, name='Test Game')
        self.client.login(username='test@example.com', password='testpass123')

    def test_create_score_leaderboard(self):
        """Test creating a standard score-based leaderboard"""
        response = self.client.post(
            reverse('leaderboards:leaderboard_create', kwargs={'game_slug': self.game.slug}),
            {'name': 'High Scores', 'leaderboard_type': 'score', 'sort_order': 'desc'}
        )
        self.assertRedirects(response, reverse('games:game_detail', kwargs={'slug': self.game.slug}))
        self.assertTrue(Leaderboard.objects.filter(name='High Scores').exists())

    def test_create_correct_answer_leaderboard(self):
        """Test creating a correct-answer leaderboard with answer"""
        response = self.client.post(
            reverse('leaderboards:leaderboard_create', kwargs={'game_slug': self.game.slug}),
            {
                'name': 'Puzzle Board',
                'leaderboard_type': 'correct_answer',
                'correct_answer': 'the answer',
                'sort_order': 'newest'
            }
        )
        self.assertRedirects(response, reverse('games:game_detail', kwargs={'slug': self.game.slug}))
        leaderboard = Leaderboard.objects.get(name='Puzzle Board')
        self.assertEqual(leaderboard.leaderboard_type, 'correct_answer')
        self.assertEqual(leaderboard.correct_answer, 'the answer')

    def test_create_correct_answer_leaderboard_requires_answer(self):
        """Test that correct_answer type requires the answer field"""
        response = self.client.post(
            reverse('leaderboards:leaderboard_create', kwargs={'game_slug': self.game.slug}),
            {
                'name': 'Puzzle Board',
                'leaderboard_type': 'correct_answer',
                'sort_order': 'newest'
            }
        )
        # Should redirect but NOT create the leaderboard
        self.assertRedirects(response, reverse('games:game_detail', kwargs={'slug': self.game.slug}))
        self.assertFalse(Leaderboard.objects.filter(name='Puzzle Board').exists())

    def test_create_leaderboard_with_display_options(self):
        """Test creating leaderboard with display options"""
        response = self.client.post(
            reverse('leaderboards:leaderboard_create', kwargs={'game_slug': self.game.slug}),
            {
                'name': 'Custom Board',
                'leaderboard_type': 'score',
                'sort_order': 'desc',
                'show_score': False,
                'show_date': True
            }
        )
        self.assertRedirects(response, reverse('games:game_detail', kwargs={'slug': self.game.slug}))
        leaderboard = Leaderboard.objects.get(name='Custom Board')
        self.assertFalse(leaderboard.show_score)
        self.assertTrue(leaderboard.show_date)


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


class RetentionPolicyTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        self.game = Game.objects.create(owner=self.user, name='Test Game')
        self.leaderboard = Leaderboard.objects.create(
            game=self.game,
            name='Test Leaderboard',
            min_scores_to_keep=3,
            max_scores=10
        )

    def test_default_retention_values(self):
        """Test that new leaderboards have default retention values"""
        lb = Leaderboard.objects.create(game=self.game, name='Default Board')
        self.assertEqual(lb.min_scores_to_keep, 10)
        self.assertEqual(lb.max_scores, 1000)

    def test_prune_excess_scores_desc(self):
        """Test that prune_excess_scores keeps best scores for desc order"""
        self.leaderboard.max_scores = 5
        self.leaderboard.save()

        # Create 8 scores (more than max_scores=5)
        for i in range(8):
            Score.objects.create(
                leaderboard=self.leaderboard,
                player_name=f'Player{i}',
                score=i * 100
            )

        self.assertEqual(self.leaderboard.scores.count(), 8)
        self.leaderboard.prune_excess_scores()
        self.assertEqual(self.leaderboard.scores.count(), 5)

        # Should keep the 5 highest scores (300, 400, 500, 600, 700)
        remaining_scores = list(self.leaderboard.scores.order_by('-score').values_list('score', flat=True))
        self.assertEqual(remaining_scores, [700, 600, 500, 400, 300])

    def test_prune_excess_scores_asc(self):
        """Test that prune_excess_scores keeps best scores for asc order (lower is better)"""
        self.leaderboard.sort_order = 'asc'
        self.leaderboard.max_scores = 3
        self.leaderboard.save()

        for i in range(5):
            Score.objects.create(
                leaderboard=self.leaderboard,
                player_name=f'Player{i}',
                score=i * 100
            )

        self.leaderboard.prune_excess_scores()
        self.assertEqual(self.leaderboard.scores.count(), 3)

        # Should keep lowest 3 scores (0, 100, 200)
        remaining_scores = list(self.leaderboard.scores.order_by('score').values_list('score', flat=True))
        self.assertEqual(remaining_scores, [0, 100, 200])

    def test_cleanup_respects_min_scores_to_keep(self):
        """Test that cleanup command preserves min_scores_to_keep even if expired"""
        from django.core.management import call_command

        # Create 5 expired scores
        for i in range(5):
            score = Score.objects.create(
                leaderboard=self.leaderboard,
                player_name=f'Player{i}',
                score=i * 100
            )
            score.expires_at = timezone.now() - timedelta(days=1)
            score.save()

        self.assertEqual(self.leaderboard.scores.count(), 5)

        # Run cleanup - should keep top 3 (min_scores_to_keep=3)
        call_command('cleanup_expired_scores')

        self.assertEqual(self.leaderboard.scores.count(), 3)
        # Should keep highest 3 scores (200, 300, 400)
        remaining_scores = list(self.leaderboard.scores.order_by('-score').values_list('score', flat=True))
        self.assertEqual(remaining_scores, [400, 300, 200])

    def test_cleanup_deletes_expired_beyond_min(self):
        """Test that cleanup deletes expired scores beyond min_scores_to_keep.

        Protection is based on recency (most recent scores kept), not score value.
        This ensures cheater scores with inflated values eventually age out.
        """
        from django.core.management import call_command

        # Create 3 older expired scores (created first = older)
        for i in range(3):
            score = Score.objects.create(
                leaderboard=self.leaderboard,
                player_name=f'Old{i}',
                score=(i + 10) * 100  # Higher scores, but older
            )
            score.expires_at = timezone.now() - timedelta(days=1)
            score.save()

        # Create 3 recent expired scores (created last = newer, protected)
        for i in range(3):
            score = Score.objects.create(
                leaderboard=self.leaderboard,
                player_name=f'Recent{i}',
                score=i * 100  # Lower scores, but more recent
            )
            score.expires_at = timezone.now() - timedelta(days=1)
            score.save()

        self.assertEqual(self.leaderboard.scores.count(), 6)

        # Run cleanup - protects most recent 3 scores regardless of value
        # Older expired scores should be deleted
        call_command('cleanup_expired_scores')

        # The 3 most recent scores should remain (protected by recency)
        self.assertEqual(self.leaderboard.scores.count(), 3)
        for score in self.leaderboard.scores.all():
            self.assertIn('Recent', score.player_name)


class RetentionFormAccessTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        self.game = Game.objects.create(owner=self.user, name='Test Game')
        self.leaderboard = Leaderboard.objects.create(game=self.game, name='Test Board')
        self.client.login(username='test@example.com', password='testpass123')

    def test_regular_user_cannot_see_retention_fields(self):
        """Test that users without can_customize don't see retention fields"""
        response = self.client.get(reverse('leaderboards:leaderboard_edit', kwargs={
            'game_slug': self.game.slug,
            'leaderboard_slug': self.leaderboard.slug
        }))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Minimum Scores to Keep')
        self.assertNotContains(response, 'Maximum Scores')

    def test_customize_user_can_see_retention_fields(self):
        """Test that users with can_customize see retention fields"""
        self.user.can_customize = True
        self.user.save()

        response = self.client.get(reverse('leaderboards:leaderboard_edit', kwargs={
            'game_slug': self.game.slug,
            'leaderboard_slug': self.leaderboard.slug
        }))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Minimum Scores to Keep')
        self.assertContains(response, 'Maximum Scores')

    def test_customize_user_can_update_retention(self):
        """Test that users with can_customize can update retention settings"""
        self.user.can_customize = True
        self.user.save()

        response = self.client.post(
            reverse('leaderboards:leaderboard_edit', kwargs={
                'game_slug': self.game.slug,
                'leaderboard_slug': self.leaderboard.slug
            }),
            {
                'name': 'Test Board',
                'leaderboard_type': 'score',
                'sort_order': 'desc',
                'min_scores_to_keep': 20,
                'max_scores': 500
            }
        )
        self.leaderboard.refresh_from_db()
        self.assertEqual(self.leaderboard.min_scores_to_keep, 20)
        self.assertEqual(self.leaderboard.max_scores, 500)
