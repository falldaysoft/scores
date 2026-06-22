"""WebAuthn (passkey) registration and login endpoints.

Browser side uses @simplewebauthn/browser, whose option/response JSON matches
py_webauthn's options_to_json() / verify_* helpers exactly.
"""
import json

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse, HttpResponseBadRequest
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.views import View

from webauthn import (
    generate_authentication_options,
    generate_registration_options,
    options_to_json,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers import base64url_to_bytes, bytes_to_base64url
from webauthn.helpers.exceptions import (
    InvalidAuthenticationResponse,
    InvalidRegistrationResponse,
)
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from .models import WebAuthnCredential

REG_CHALLENGE_KEY = 'webauthn_register_challenge'
AUTH_CHALLENGE_KEY = 'webauthn_auth_challenge'


class PasskeyRegisterBeginView(LoginRequiredMixin, View):
    """Issue registration options for the logged-in user (called from Settings)."""

    def post(self, request):
        user = request.user
        exclude_credentials = [
            PublicKeyCredentialDescriptor(id=base64url_to_bytes(c.credential_id))
            for c in user.passkeys.all()
        ]
        options = generate_registration_options(
            rp_id=settings.WEBAUTHN_RP_ID,
            rp_name=settings.WEBAUTHN_RP_NAME,
            user_id=user.get_webauthn_user_handle().encode('utf-8'),
            user_name=user.email,
            user_display_name=user.account_name or user.email,
            exclude_credentials=exclude_credentials,
            authenticator_selection=AuthenticatorSelectionCriteria(
                resident_key=ResidentKeyRequirement.PREFERRED,
                user_verification=UserVerificationRequirement.PREFERRED,
            ),
        )
        request.session[REG_CHALLENGE_KEY] = bytes_to_base64url(options.challenge)
        return JsonResponse(json.loads(options_to_json(options)))


class PasskeyRegisterCompleteView(LoginRequiredMixin, View):
    """Verify the attestation and store the new credential."""

    def post(self, request):
        challenge = request.session.pop(REG_CHALLENGE_KEY, None)
        if not challenge:
            return HttpResponseBadRequest('No registration in progress')

        try:
            body = json.loads(request.body)
        except json.JSONDecodeError:
            return HttpResponseBadRequest('Invalid request body')

        attestation = body.get('credential')
        name = (body.get('name') or '').strip()[:100] or 'Passkey'

        try:
            verification = verify_registration_response(
                credential=json.dumps(attestation),
                expected_challenge=base64url_to_bytes(challenge),
                expected_rp_id=settings.WEBAUTHN_RP_ID,
                expected_origin=settings.WEBAUTHN_ORIGIN,
                require_user_verification=False,
            )
        except (InvalidRegistrationResponse, ValueError, KeyError) as exc:
            return JsonResponse({'error': f'Registration failed: {exc}'}, status=400)

        credential_id = bytes_to_base64url(verification.credential_id)
        if WebAuthnCredential.objects.filter(credential_id=credential_id).exists():
            return JsonResponse({'error': 'This passkey is already registered.'}, status=400)

        transports = (attestation or {}).get('response', {}).get('transports') or []
        WebAuthnCredential.objects.create(
            user=request.user,
            credential_id=credential_id,
            public_key=bytes_to_base64url(verification.credential_public_key),
            sign_count=verification.sign_count,
            transports=transports,
            name=name,
        )
        return JsonResponse({'ok': True})


class PasskeyAuthBeginView(View):
    """Issue authentication options for usernameless (discoverable) login."""

    def post(self, request):
        options = generate_authentication_options(
            rp_id=settings.WEBAUTHN_RP_ID,
            user_verification=UserVerificationRequirement.PREFERRED,
        )
        request.session[AUTH_CHALLENGE_KEY] = bytes_to_base64url(options.challenge)
        return JsonResponse(json.loads(options_to_json(options)))


class PasskeyAuthCompleteView(View):
    """Verify the assertion, then log the matching user in."""

    def post(self, request):
        challenge = request.session.pop(AUTH_CHALLENGE_KEY, None)
        if not challenge:
            return HttpResponseBadRequest('No authentication in progress')

        try:
            body = json.loads(request.body)
        except json.JSONDecodeError:
            return HttpResponseBadRequest('Invalid request body')

        credential_id = body.get('id')
        try:
            credential = WebAuthnCredential.objects.select_related('user').get(
                credential_id=credential_id
            )
        except WebAuthnCredential.DoesNotExist:
            return JsonResponse({'error': 'Unknown passkey.'}, status=400)

        try:
            verification = verify_authentication_response(
                credential=json.dumps(body),
                expected_challenge=base64url_to_bytes(challenge),
                expected_rp_id=settings.WEBAUTHN_RP_ID,
                expected_origin=settings.WEBAUTHN_ORIGIN,
                credential_public_key=base64url_to_bytes(credential.public_key),
                credential_current_sign_count=credential.sign_count,
                require_user_verification=False,
            )
        except (InvalidAuthenticationResponse, ValueError, KeyError) as exc:
            return JsonResponse({'error': f'Authentication failed: {exc}'}, status=400)

        user = credential.user
        if not user.is_active:
            return JsonResponse({'error': 'This account is disabled.'}, status=403)

        credential.sign_count = verification.new_sign_count
        credential.last_used_at = timezone.now()
        credential.save(update_fields=['sign_count', 'last_used_at'])

        login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        return JsonResponse({'ok': True, 'redirect': reverse('games:dashboard')})


class PasskeyDeleteView(LoginRequiredMixin, View):
    """Remove one of the current user's passkeys."""

    def post(self, request, pk):
        deleted, _ = WebAuthnCredential.objects.filter(user=request.user, pk=pk).delete()
        if deleted:
            messages.success(request, 'Passkey removed.')
        else:
            messages.error(request, 'Passkey not found.')
        return redirect('accounts:settings')
