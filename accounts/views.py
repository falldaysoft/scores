from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib import messages
from django.core.mail import send_mail
from django.conf import settings
from django.urls import reverse
from django.views import View

from .forms import SignupForm, LoginForm
from .models import User


class SignupView(View):
    def get(self, request):
        if request.user.is_authenticated:
            return redirect('games:dashboard')
        form = SignupForm()
        return render(request, 'accounts/signup.html', {'form': form})

    def post(self, request):
        form = SignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            token = user.generate_verification_token()
            self.send_verification_email(request, user, token)
            login(request, user)
            messages.success(request, 'Account created! Please check your email to verify your account.')
            return redirect('games:dashboard')
        return render(request, 'accounts/signup.html', {'form': form})

    def send_verification_email(self, request, user, token):
        verification_url = request.build_absolute_uri(
            reverse('accounts:verify_email', kwargs={'token': token})
        )
        send_mail(
            subject='Verify your Scores email address',
            message=f'Click this link to verify your email: {verification_url}',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=f'''
                <h2>Welcome to Scores!</h2>
                <p>Click the button below to verify your email address:</p>
                <p><a href="{verification_url}" style="display:inline-block;padding:12px 24px;background:#4f46e5;color:white;text-decoration:none;border-radius:8px;">Verify Email</a></p>
                <p>Or copy this link: {verification_url}</p>
            ''',
        )


class CustomLoginView(LoginView):
    form_class = LoginForm
    template_name = 'accounts/login.html'

    def get_success_url(self):
        return reverse('games:dashboard')


class CustomLogoutView(LogoutView):
    next_page = 'home'


class VerifyEmailView(View):
    def get(self, request, token):
        try:
            user = User.objects.get(email_verification_token=token)
            if user.verify_email(token):
                messages.success(request, 'Email verified successfully!')
            else:
                messages.error(request, 'Invalid verification token.')
        except User.DoesNotExist:
            messages.error(request, 'Invalid verification token.')
        return redirect('games:dashboard' if request.user.is_authenticated else 'accounts:login')


class ResendVerificationView(View):
    def post(self, request):
        if request.user.is_authenticated and not request.user.email_verified:
            token = request.user.generate_verification_token()
            SignupView().send_verification_email(request, request.user, token)
            messages.success(request, 'Verification email sent!')
        return redirect('games:dashboard')
