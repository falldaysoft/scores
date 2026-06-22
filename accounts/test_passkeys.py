"""Tests for WebAuthn passkey registration and login.

The end-to-end ceremony tests drive a minimal in-process software
authenticator (`SoftAuthenticator`) built on `cryptography` + `cbor2` — both
already runtime dependencies — so no extra test packages are required.
"""
import hashlib
import json
import os
from struct import pack

import cbor2
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec

from django.test import TestCase, Client
from django.urls import reverse

from webauthn.helpers import base64url_to_bytes, bytes_to_base64url

from .models import User, WebAuthnCredential

ORIGIN = 'http://localhost:8000'


class SoftAuthenticator:
    """A minimal ES256 software authenticator producing SimpleWebAuthn-shaped JSON."""

    AAGUID = b'\x00' * 16

    def __init__(self):
        self.credential_id = os.urandom(32)
        self.private_key = ec.generate_private_key(ec.SECP256R1())
        self.rp_id = None
        self.user_handle = None
        self.sign_count = 0

    def _cose_public_key(self):
        nums = self.private_key.public_key().public_numbers()
        # COSE_Key for ES256: kty=EC2(2), alg=ES256(-7), crv=P-256(1), x, y
        return cbor2.dumps({
            1: 2,
            3: -7,
            -1: 1,
            -2: nums.x.to_bytes(32, 'big'),
            -3: nums.y.to_bytes(32, 'big'),
        })

    def create(self, options, origin=ORIGIN):
        """Build an attestation response for a registration options dict."""
        self.rp_id = options['rp']['id']
        self.user_handle = base64url_to_bytes(options['user']['id'])
        client_data = json.dumps({
            'type': 'webauthn.create',
            'challenge': options['challenge'],
            'origin': origin,
        }).encode()

        rp_id_hash = hashlib.sha256(self.rp_id.encode()).digest()
        flags = b'\x45'  # UP | UV | AT
        cose_key = self._cose_public_key()
        auth_data = (
            rp_id_hash + flags + pack('>I', self.sign_count)
            + self.AAGUID + pack('>H', len(self.credential_id))
            + self.credential_id + cose_key
        )
        attestation_object = cbor2.dumps({
            'fmt': 'none',
            'attStmt': {},
            'authData': auth_data,
        })
        return {
            'id': bytes_to_base64url(self.credential_id),
            'rawId': bytes_to_base64url(self.credential_id),
            'response': {
                'clientDataJSON': bytes_to_base64url(client_data),
                'attestationObject': bytes_to_base64url(attestation_object),
                'transports': ['internal'],
            },
            'type': 'public-key',
            'clientExtensionResults': {},
        }

    def get(self, options, origin=ORIGIN):
        """Build an assertion response for an authentication options dict."""
        self.sign_count += 1
        client_data = json.dumps({
            'type': 'webauthn.get',
            'challenge': options['challenge'],
            'origin': origin,
        }).encode()
        rp_id_hash = hashlib.sha256(options['rpId'].encode()).digest()
        flags = b'\x05'  # UP | UV
        auth_data = rp_id_hash + flags + pack('>I', self.sign_count)
        signature = self.private_key.sign(
            auth_data + hashlib.sha256(client_data).digest(),
            ec.ECDSA(hashes.SHA256()),
        )
        return {
            'id': bytes_to_base64url(self.credential_id),
            'rawId': bytes_to_base64url(self.credential_id),
            'response': {
                'authenticatorData': bytes_to_base64url(auth_data),
                'clientDataJSON': bytes_to_base64url(client_data),
                'signature': bytes_to_base64url(signature),
                'userHandle': bytes_to_base64url(self.user_handle) if self.user_handle else None,
            },
            'type': 'public-key',
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
    """Full register + login ceremony against the software authenticator."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(email='e2e@example.com', password='pw123456')

    def _register(self, device, name='Test key'):
        self.client.login(username='e2e@example.com', password='pw123456')
        begin = self.client.post(reverse('accounts:passkey_register_begin')).json()
        attestation = device.create(begin)
        return self.client.post(
            reverse('accounts:passkey_register_complete'),
            data=json.dumps({'credential': attestation, 'name': name}),
            content_type='application/json',
        )

    def test_register_then_login(self):
        device = SoftAuthenticator()

        # --- Registration (authenticated) ---
        resp = self._register(device, name='My YubiKey')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertTrue(resp.json().get('ok'))
        cred = WebAuthnCredential.objects.get(user=self.user)
        self.assertEqual(cred.name, 'My YubiKey')
        self.assertEqual(cred.sign_count, 0)
        self.assertEqual(cred.transports, ['internal'])

        # Log out before testing passkey login.
        self.client.logout()

        # --- Login (anonymous, usernameless) ---
        begin = self.client.post(reverse('accounts:passkey_login_begin')).json()
        assertion = device.get(begin)
        resp = self.client.post(
            reverse('accounts:passkey_login_complete'),
            data=json.dumps(assertion),
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
        device = SoftAuthenticator()
        self._register(device)
        self.client.logout()

        self.client.post(reverse('accounts:passkey_login_begin'))
        # Sign a *different* challenge than the server stored.
        forged = {'rpId': 'localhost', 'challenge': bytes_to_base64url(b'not-the-real-challenge')}
        assertion = device.get(forged)
        resp = self.client.post(
            reverse('accounts:passkey_login_complete'),
            data=json.dumps(assertion),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 400)
        self.assertNotIn('_auth_user_id', self.client.session)
