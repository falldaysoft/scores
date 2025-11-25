from django.test import TestCase, Client
from django.urls import reverse
from accounts.models import User
from .models import Game


class GameModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            username='testuser',
            password='testpass123'
        )

    def test_create_game(self):
        game = Game.objects.create(
            owner=self.user,
            name='Test Game',
            description='A test game'
        )
        self.assertEqual(game.slug, 'test-game')
        self.assertEqual(str(game), 'Test Game')

    def test_auto_slug_generation(self):
        game = Game.objects.create(
            owner=self.user,
            name='My Awesome Game!'
        )
        self.assertEqual(game.slug, 'my-awesome-game')

    def test_unique_slug_per_user(self):
        Game.objects.create(owner=self.user, name='Test Game')
        # Same user can't have same slug
        with self.assertRaises(Exception):
            Game.objects.create(owner=self.user, name='Test Game', slug='test-game')


class DashboardViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            email='test@example.com',
            username='testuser',
            password='testpass123'
        )

    def test_dashboard_requires_login(self):
        response = self.client.get(reverse('games:dashboard'))
        self.assertRedirects(response, f"{reverse('accounts:login')}?next={reverse('games:dashboard')}")

    def test_dashboard_loads_for_logged_in_user(self):
        self.client.login(username='test@example.com', password='testpass123')
        response = self.client.get(reverse('games:dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Your Games')

    def test_dashboard_shows_user_games(self):
        self.client.login(username='test@example.com', password='testpass123')
        Game.objects.create(owner=self.user, name='My Game')
        response = self.client.get(reverse('games:dashboard'))
        self.assertContains(response, 'My Game')


class GameCreateViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            email='test@example.com',
            username='testuser',
            password='testpass123'
        )
        self.client.login(username='test@example.com', password='testpass123')

    def test_create_game_form_loads(self):
        response = self.client.get(reverse('games:game_create'))
        self.assertEqual(response.status_code, 200)

    def test_create_game_success(self):
        response = self.client.post(reverse('games:game_create'), {
            'name': 'New Game',
            'description': 'A new game',
        })
        self.assertTrue(Game.objects.filter(name='New Game').exists())
        game = Game.objects.get(name='New Game')
        self.assertRedirects(response, reverse('games:game_detail', kwargs={'slug': game.slug}))


class GameDetailViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            email='test@example.com',
            username='testuser',
            password='testpass123'
        )
        self.game = Game.objects.create(owner=self.user, name='Test Game')
        self.client.login(username='test@example.com', password='testpass123')

    def test_game_detail_loads(self):
        response = self.client.get(reverse('games:game_detail', kwargs={'slug': self.game.slug}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Game')

    def test_game_detail_shows_public_url(self):
        response = self.client.get(reverse('games:game_detail', kwargs={'slug': self.game.slug}))
        self.assertContains(response, f'/games/{self.game.slug}/')

    def test_cannot_view_other_users_game(self):
        other_user = User.objects.create_user(
            email='other@example.com',
            username='otheruser',
            password='testpass123'
        )
        other_game = Game.objects.create(owner=other_user, name='Other Game')
        response = self.client.get(reverse('games:game_detail', kwargs={'slug': other_game.slug}))
        self.assertEqual(response.status_code, 404)


class GameDeleteViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            email='test@example.com',
            username='testuser',
            password='testpass123'
        )
        self.game = Game.objects.create(owner=self.user, name='Test Game')
        self.client.login(username='test@example.com', password='testpass123')

    def test_delete_game(self):
        response = self.client.post(reverse('games:game_delete', kwargs={'slug': self.game.slug}))
        self.assertRedirects(response, reverse('games:dashboard'))
        self.assertFalse(Game.objects.filter(pk=self.game.pk).exists())
