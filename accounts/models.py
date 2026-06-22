import secrets
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('Email is required')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)
    account_name = models.CharField(max_length=100, unique=True, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    can_customize = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)
    email_verified = models.BooleanField(default=False)
    email_verification_token = models.CharField(max_length=64, blank=True)
    email_verification_sent_at = models.DateTimeField(null=True, blank=True)

    # Stable per-user WebAuthn user handle (base64url of random bytes), populated lazily.
    webauthn_user_handle = models.CharField(max_length=128, blank=True)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    def get_webauthn_user_handle(self):
        """Return this user's WebAuthn user handle, creating one if needed."""
        if not self.webauthn_user_handle:
            self.webauthn_user_handle = secrets.token_urlsafe(32)
            self.save(update_fields=['webauthn_user_handle'])
        return self.webauthn_user_handle

    def generate_verification_token(self):
        self.email_verification_token = secrets.token_urlsafe(32)
        self.email_verification_sent_at = timezone.now()
        self.save(update_fields=['email_verification_token', 'email_verification_sent_at'])
        return self.email_verification_token

    def verify_email(self, token):
        if self.email_verification_token == token:
            self.email_verified = True
            self.email_verification_token = ''
            self.save(update_fields=['email_verified', 'email_verification_token'])
            return True
        return False


class WebAuthnCredential(models.Model):
    """A WebAuthn (passkey) credential registered to a user."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='passkeys')
    # base64url-encoded credential id (raw bytes encoded), unique across all users.
    credential_id = models.CharField(max_length=512, unique=True)
    # base64url-encoded COSE public key.
    public_key = models.TextField()
    sign_count = models.PositiveBigIntegerField(default=0)
    # Authenticator transports reported at registration (e.g. ["internal", "hybrid"]).
    transports = models.JSONField(default=list, blank=True)
    name = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.name or "Passkey"} ({self.user.email})'
