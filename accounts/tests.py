from django.test import TestCase, Client
from django.urls import reverse
from django.core import mail
from .models import User


class UserModelTest(TestCase):
    def test_create_user(self):
        user = User.objects.create_user(
            email='test@example.com',
            username='testuser',
            password='testpass123'
        )
        self.assertEqual(user.email, 'test@example.com')
        self.assertFalse(user.email_verified)

    def test_generate_verification_token(self):
        user = User.objects.create_user(
            email='test@example.com',
            username='testuser',
            password='testpass123'
        )
        token = user.generate_verification_token()
        self.assertTrue(len(token) > 20)
        self.assertEqual(user.email_verification_token, token)

    def test_verify_email(self):
        user = User.objects.create_user(
            email='test@example.com',
            username='testuser',
            password='testpass123'
        )
        token = user.generate_verification_token()
        self.assertTrue(user.verify_email(token))
        self.assertTrue(user.email_verified)
        self.assertEqual(user.email_verification_token, '')

    def test_verify_email_wrong_token(self):
        user = User.objects.create_user(
            email='test@example.com',
            username='testuser',
            password='testpass123'
        )
        user.generate_verification_token()
        self.assertFalse(user.verify_email('wrong-token'))
        self.assertFalse(user.email_verified)


class SignupViewTest(TestCase):
    def setUp(self):
        self.client = Client()

    def test_signup_page_loads(self):
        response = self.client.get(reverse('accounts:signup'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Create an account')

    def test_signup_success(self):
        response = self.client.post(reverse('accounts:signup'), {
            'email': 'newuser@example.com',
            'username': 'newuser',
            'password1': 'SecurePass123!',
            'password2': 'SecurePass123!',
        })
        self.assertRedirects(response, reverse('games:dashboard'))
        self.assertTrue(User.objects.filter(email='newuser@example.com').exists())
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Verify', mail.outbox[0].subject)

    def test_signup_duplicate_email(self):
        User.objects.create_user(
            email='existing@example.com',
            username='existing',
            password='testpass123'
        )
        response = self.client.post(reverse('accounts:signup'), {
            'email': 'existing@example.com',
            'username': 'newuser',
            'password1': 'SecurePass123!',
            'password2': 'SecurePass123!',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'already exists')


class LoginViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            email='test@example.com',
            username='testuser',
            password='testpass123'
        )

    def test_login_page_loads(self):
        response = self.client.get(reverse('accounts:login'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Sign in')

    def test_login_success(self):
        response = self.client.post(reverse('accounts:login'), {
            'username': 'test@example.com',
            'password': 'testpass123',
        })
        self.assertRedirects(response, reverse('games:dashboard'))

    def test_login_wrong_password(self):
        response = self.client.post(reverse('accounts:login'), {
            'username': 'test@example.com',
            'password': 'wrongpassword',
        })
        self.assertEqual(response.status_code, 200)


class EmailVerificationTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            email='test@example.com',
            username='testuser',
            password='testpass123'
        )

    def test_verify_email_success(self):
        token = self.user.generate_verification_token()
        response = self.client.get(reverse('accounts:verify_email', kwargs={'token': token}))
        self.assertRedirects(response, reverse('accounts:login'))
        self.user.refresh_from_db()
        self.assertTrue(self.user.email_verified)

    def test_verify_email_invalid_token(self):
        response = self.client.get(reverse('accounts:verify_email', kwargs={'token': 'invalid-token'}))
        self.assertRedirects(response, reverse('accounts:login'))
        self.user.refresh_from_db()
        self.assertFalse(self.user.email_verified)
