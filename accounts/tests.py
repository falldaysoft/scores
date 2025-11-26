from django.test import TestCase, Client
from django.urls import reverse
from django.core import mail
from .models import User


class UserModelTest(TestCase):
    def test_create_user(self):
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        self.assertEqual(user.email, 'test@example.com')
        self.assertFalse(user.email_verified)

    def test_generate_verification_token(self):
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        token = user.generate_verification_token()
        self.assertTrue(len(token) > 20)
        self.assertEqual(user.email_verification_token, token)

    def test_verify_email(self):
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        token = user.generate_verification_token()
        self.assertTrue(user.verify_email(token))
        self.assertTrue(user.email_verified)
        self.assertEqual(user.email_verification_token, '')

    def test_verify_email_wrong_token(self):
        user = User.objects.create_user(
            email='test@example.com',
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
            'account_name': 'NewStudio',
            'password1': 'SecurePass123!',
            'password2': 'SecurePass123!',
        })
        self.assertRedirects(response, reverse('games:dashboard'))
        user = User.objects.get(email='newuser@example.com')
        self.assertEqual(user.account_name, 'NewStudio')
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Verify', mail.outbox[0].subject)

    def test_signup_duplicate_email(self):
        User.objects.create_user(
            email='existing@example.com',
            password='testpass123'
        )
        response = self.client.post(reverse('accounts:signup'), {
            'email': 'existing@example.com',
            'account_name': 'SomeStudio',
            'password1': 'SecurePass123!',
            'password2': 'SecurePass123!',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'already exists')

    def test_signup_duplicate_account_name(self):
        User.objects.create_user(
            email='existing@example.com',
            password='testpass123',
            account_name='TakenStudio'
        )
        response = self.client.post(reverse('accounts:signup'), {
            'email': 'newuser@example.com',
            'account_name': 'TakenStudio',
            'password1': 'SecurePass123!',
            'password2': 'SecurePass123!',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'already taken')

    def test_signup_account_name_required(self):
        response = self.client.post(reverse('accounts:signup'), {
            'email': 'newuser@example.com',
            'account_name': '',
            'password1': 'SecurePass123!',
            'password2': 'SecurePass123!',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(email='newuser@example.com').exists())


class LoginViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            email='test@example.com',
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


class AccountNameTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )

    def test_account_name_initially_null(self):
        self.assertIsNone(self.user.account_name)

    def test_set_account_name(self):
        self.user.account_name = 'MyStudio'
        self.user.save()
        self.user.refresh_from_db()
        self.assertEqual(self.user.account_name, 'MyStudio')

    def test_account_name_unique(self):
        self.user.account_name = 'UniqueStudio'
        self.user.save()
        user2 = User.objects.create_user(
            email='test2@example.com',
            password='testpass123'
        )
        from django.db import IntegrityError
        user2.account_name = 'UniqueStudio'
        with self.assertRaises(IntegrityError):
            user2.save()


class AccountSettingsViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )

    def test_settings_page_requires_login(self):
        response = self.client.get(reverse('accounts:settings'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)

    def test_settings_page_loads(self):
        self.client.login(username='test@example.com', password='testpass123')
        response = self.client.get(reverse('accounts:settings'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Account Settings')

    def test_update_account_name(self):
        self.client.login(username='test@example.com', password='testpass123')
        response = self.client.post(reverse('accounts:settings'), {
            'account_name': 'NewStudio'
        })
        self.assertRedirects(response, reverse('accounts:settings'))
        self.user.refresh_from_db()
        self.assertEqual(self.user.account_name, 'NewStudio')

    def test_update_account_name_duplicate(self):
        User.objects.create_user(
            email='other@example.com',
            password='testpass123',
            account_name='TakenName'
        )
        self.client.login(username='test@example.com', password='testpass123')
        response = self.client.post(reverse('accounts:settings'), {
            'account_name': 'TakenName'
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'already taken')

    def test_update_account_name_case_insensitive_duplicate(self):
        User.objects.create_user(
            email='other@example.com',
            password='testpass123',
            account_name='TakenName'
        )
        self.client.login(username='test@example.com', password='testpass123')
        response = self.client.post(reverse('accounts:settings'), {
            'account_name': 'takenname'
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'already taken')

    def test_clear_account_name(self):
        self.user.account_name = 'OldName'
        self.user.save()
        self.client.login(username='test@example.com', password='testpass123')
        response = self.client.post(reverse('accounts:settings'), {
            'account_name': ''
        })
        self.assertRedirects(response, reverse('accounts:settings'))
        self.user.refresh_from_db()
        self.assertIsNone(self.user.account_name)
