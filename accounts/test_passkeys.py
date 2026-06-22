"""Tests for WebAuthn passkey registration and login.

The end-to-end ceremony tests use `soft-webauthn` (a software authenticator).
They are skipped if that package isn't installed; the non-crypto branch tests
always run.
"""
import json

from django.test import TestCase, Client
from django.urls import reverse

from webauthn.helpers import base64url_to_bytes, bytes_to_base64url

from .models import User, WebAuthnCredential

try:
    from soft_webauthn import SoftWebauthnDevice
    HAS_SOFT_WEBAUTHN = True
except ImportError:  # pragma: no cover
    HAS_SOFT_WEBAUTHN = False

ORIGIN = 'http://localhost:8000'


def _creation_options_for_device(options_json):
    """Convert our begin-registration JSON into soft-webauthn's create() input."""
    pk = {
        'rp': options_json['rp'],
        'user': {
            'id': base64url_to_bytes(options_json['user']['id']),
            'name': options_json['user']['name'],
            'displayName': options_json['user']['displayName'],
        },
        'challenge': base64url_to_bytes(options_json['challenge']),
        'pubKeyCredParams': options_json['pubKeyCredParams'],
        'attestation': options_json.get('attestation', 'none'),
    }
    if options_json.get('excludeCredentials'):
        pk['excludeCredentials'] = [
            {'type': c['type'], 'id': base64url_to_bytes(c['id'])}
            for c in options_json['excludeCredentials']
        ]
    return {'publicKey': pk}


def _request_options_for_device(options_json):
    """Convert our begin-login JSON into soft-webauthn's get() input."""
    pk = {
        'challenge': base64url_to_bytes(options_json['challenge']),
        'rpId': options_json['rpId'],
        'userVerification': options_json.get('userVerification', 'preferred'),
    }
    if options_json.get('allowCredentials'):
        pk['allowCredentials'] = [
            {'type': c['type'], 'id': base64url_to_bytes(c['id'])}
            for c in options_json['allowCredentials']
        ]
    return {'publicKey': pk}


def _attestation_to_json(att):
    return {
        'id': bytes_to_base64url(att['rawId']),
        'rawId': bytes_to_base64url(att['rawId']),
        'response': {
            'clientDataJSON': bytes_to_base64url(att['response']['clientDataJSON']),
            'attestationObject': bytes_to_base64url(att['response']['attestationObject']),
            'transports': ['internal'],
        },
        'type': att['type'],
        'clientExtensionResults': {},
    }


def _assertion_to_json(ass):
    user_handle = ass['response'].get('userHandle')
    return {
        'id': bytes_to_base64url(ass['rawId']),
        'rawId': bytes_to_base64url(ass['rawId']),
        'response': {
            'authenticatorData': bytes_to_base64url(ass['response']['authenticatorData']),
            'clientDataJSON': bytes_to_base64url(ass['response']['clientDataJSON']),
            'signature': bytes_to_base64url(ass['response']['signature']),
            'userHandle': bytes_to_base64url(user_handle) if user_handle else None,
        },
        'type': ass['type'],
        'clientExtensionResults': {},
    }


class WebAuthnModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='m@example.com', password='pw123456')

    def test_user_handle_is_stable_and_created_lazily(self):
        self.assertEqual(self.user.webauthn_user_handle, '')
        handle = self.user.get_webauthn_user_handle()
        self.assertTrue(handle)
        self.assertEqual(handle, self.user.get_webauthn_user_handle())
        self.user.refresh_from_db()
        self.assertEqual(self.user.webauthn_user_handle, handle)

    def test_credential_str(self):
        cred = WebAuthnCredential.objects.create(
            user=self.user, credential_id='abc', public_key='pk', name='Laptop'
        )
        self.assertIn('Laptop', str(cred))
        self.assertIn('m@example.com', str(cred))


class PasskeyRegisterViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(email='reg@example.com', password='pw123456')

    def test_begin_requires_login(self):
        resp = self.client.post(reverse('accounts:passkey_register_begin'))
        self.assertEqual(resp.status_code, 302)
        self.assertIn('login', resp.url)

    def test_begin_returns_options_and_stores_challenge(self):
        self.client.login(username='reg@example.com', password='pw123456')
        resp = self.client.post(reverse('accounts:passkey_register_begin'))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('challenge', data)
        self.assertEqual(data['rp']['id'], 'localhost')
        self.assertEqual(data['user']['name'], 'reg@example.com')
        self.assertIn('webauthn_register_challenge', self.client.session)

    def test_complete_without_challenge_is_bad_request(self):
        self.client.login(username='reg@example.com', password='pw123456')
        resp = self.client.post(
            reverse('accounts:passkey_register_complete'),
            data=json.dumps({'credential': {}}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 400)


class PasskeyLoginViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(email='log@example.com', password='pw123456')

    def test_begin_does_not_require_login_and_stores_challenge(self):
        resp = self.client.post(reverse('accounts:passkey_login_begin'))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('challenge', data)
        self.assertEqual(data['rpId'], 'localhost')
        self.assertIn('webauthn_auth_challenge', self.client.session)

    def test_complete_unknown_credential(self):
        # Seed a challenge so we get past the session guard.
        self.client.post(reverse('accounts:passkey_login_begin'))
        resp = self.client.post(
            reverse('accounts:passkey_login_complete'),
            data=json.dumps({'id': 'does-not-exist'}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn('Unknown passkey', resp.json()['error'])

    def test_complete_without_challenge_is_bad_request(self):
        resp = self.client.post(
            reverse('accounts:passkey_login_complete'),
            data=json.dumps({'id': 'x'}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 400)


class PasskeyDeleteViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(email='del@example.com', password='pw123456')
        self.other = User.objects.create_user(email='other@example.com', password='pw123456')
        self.cred = WebAuthnCredential.objects.create(
            user=self.user, credential_id='mine', public_key='pk', name='Mine'
        )

    def test_delete_requires_login(self):
        resp = self.client.post(reverse('accounts:passkey_delete', args=[self.cred.pk]))
        self.assertEqual(resp.status_code, 302)
        self.assertIn('login', resp.url)

    def test_delete_own_passkey(self):
        self.client.login(username='del@example.com', password='pw123456')
        resp = self.client.post(reverse('accounts:passkey_delete', args=[self.cred.pk]))
        self.assertRedirects(resp, reverse('accounts:settings'))
        self.assertFalse(WebAuthnCredential.objects.filter(pk=self.cred.pk).exists())

    def test_cannot_delete_other_users_passkey(self):
        other_cred = WebAuthnCredential.objects.create(
            user=self.other, credential_id='theirs', public_key='pk'
        )
        self.client.login(username='del@example.com', password='pw123456')
        self.client.post(reverse('accounts:passkey_delete', args=[other_cred.pk]))
        self.assertTrue(WebAuthnCredential.objects.filter(pk=other_cred.pk).exists())

    def test_settings_page_lists_passkeys(self):
        self.client.login(username='del@example.com', password='pw123456')
        resp = self.client.get(reverse('accounts:settings'))
        self.assertContains(resp, 'Passkeys')
        self.assertContains(resp, 'Mine')


class PasskeyEndToEndTest(TestCase):
    """Full register + login ceremony against a software authenticator."""

    def setUp(self):
        if not HAS_SOFT_WEBAUTHN:
            self.skipTest('soft-webauthn not installed')
        self.client = Client()
        self.user = User.objects.create_user(email='e2e@example.com', password='pw123456')

    def _register(self, device, name='Test key'):
        self.client.login(username='e2e@example.com', password='pw123456')
        begin = self.client.post(reverse('accounts:passkey_register_begin')).json()
        attestation = device.create(_creation_options_for_device(begin), ORIGIN)
        return self.client.post(
            reverse('accounts:passkey_register_complete'),
            data=json.dumps({'credential': _attestation_to_json(attestation), 'name': name}),
            content_type='application/json',
        )

    def test_register_then_login(self):
        device = SoftWebauthnDevice()

        # --- Registration (authenticated) ---
        resp = self._register(device, name='My YubiKey')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertTrue(resp.json().get('ok'))
        cred = WebAuthnCredential.objects.get(user=self.user)
        self.assertEqual(cred.name, 'My YubiKey')
        self.assertEqual(cred.sign_count, 0)

        # Log out before testing passkey login.
        self.client.logout()

        # --- Login (anonymous, usernameless) ---
        begin = self.client.post(reverse('accounts:passkey_login_begin')).json()
        assertion = device.get(_request_options_for_device(begin), ORIGIN)
        resp = self.client.post(
            reverse('accounts:passkey_login_complete'),
            data=json.dumps(_assertion_to_json(assertion)),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.json()['redirect'], reverse('games:dashboard'))

        # The session is now authenticated as our user.
        self.assertEqual(int(self.client.session['_auth_user_id']), self.user.pk)

        # Sign count advanced and last_used recorded.
        cred.refresh_from_db()
        self.assertEqual(cred.sign_count, 1)
        self.assertIsNotNone(cred.last_used_at)

    def test_login_fails_with_tampered_challenge(self):
        device = SoftWebauthnDevice()
        self._register(device)
        self.client.logout()

        self.client.post(reverse('accounts:passkey_login_begin'))
        # Authenticate against a *different* challenge than the server stored.
        forged = {
            'publicKey': {
                'challenge': b'not-the-real-challenge',
                'rpId': 'localhost',
                'userVerification': 'preferred',
            }
        }
        assertion = device.get(forged, ORIGIN)
        resp = self.client.post(
            reverse('accounts:passkey_login_complete'),
            data=json.dumps(_assertion_to_json(assertion)),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 400)
        self.assertNotIn('_auth_user_id', self.client.session)
