from django.urls import path
from . import views
from . import webauthn_views

app_name = 'accounts'

urlpatterns = [
    path('signup/', views.SignupView.as_view(), name='signup'),
    path('login/', views.CustomLoginView.as_view(), name='login'),
    path('logout/', views.CustomLogoutView.as_view(), name='logout'),
    path('verify/<str:token>/', views.VerifyEmailView.as_view(), name='verify_email'),
    path('resend-verification/', views.ResendVerificationView.as_view(), name='resend_verification'),
    path('settings/', views.AccountSettingsView.as_view(), name='settings'),
    path('delete/', views.AccountDeleteView.as_view(), name='delete'),
    # Passkeys / WebAuthn
    path('passkeys/register/begin/', webauthn_views.PasskeyRegisterBeginView.as_view(), name='passkey_register_begin'),
    path('passkeys/register/complete/', webauthn_views.PasskeyRegisterCompleteView.as_view(), name='passkey_register_complete'),
    path('passkeys/login/begin/', webauthn_views.PasskeyAuthBeginView.as_view(), name='passkey_login_begin'),
    path('passkeys/login/complete/', webauthn_views.PasskeyAuthCompleteView.as_view(), name='passkey_login_complete'),
    path('passkeys/<int:pk>/delete/', webauthn_views.PasskeyDeleteView.as_view(), name='passkey_delete'),
]
