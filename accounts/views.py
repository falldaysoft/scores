import secrets
import string

from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib import messages
from django.core.mail import send_mail
from django.conf import settings
from django.urls import reverse
from django.views import View
from django.http import HttpResponse

from django.contrib.auth.mixins import LoginRequiredMixin
from .forms import SignupForm, LoginForm, AccountSettingsForm, AccountDeleteConfirmForm
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


class AccountSettingsView(LoginRequiredMixin, View):
    def get(self, request):
        form = AccountSettingsForm(instance=request.user)
        return render(request, 'accounts/settings.html', self._context(request, form))

    def post(self, request):
        form = AccountSettingsForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Account settings updated.')
            return redirect('accounts:settings')
        return render(request, 'accounts/settings.html', self._context(request, form))

    def _context(self, request, form):
        return {
            'form': form,
            'passkeys': request.user.passkeys.all(),
        }


class AccountDeleteView(LoginRequiredMixin, View):
    def _generate_confirmation_code(self):
        """Generate a random 6-character alphanumeric confirmation code."""
        chars = string.ascii_uppercase + string.digits
        return ''.join(secrets.choice(chars) for _ in range(6))

    def _get_confirmation_code(self, request):
        """Get or create a confirmation code for this session."""
        if 'delete_confirmation_code' not in request.session:
            request.session['delete_confirmation_code'] = self._generate_confirmation_code()
        return request.session['delete_confirmation_code']

    def _get_data_counts(self, user):
        """Count all data that will be deleted with the account."""
        games = user.games.all()
        game_count = games.count()
        leaderboard_count = sum(g.leaderboards.count() for g in games)
        score_count = sum(lb.scores.count() for g in games for lb in g.leaderboards.all())
        return {
            'game_count': game_count,
            'leaderboard_count': leaderboard_count,
            'score_count': score_count,
        }

    def get(self, request):
        confirmation_code = self._get_confirmation_code(request)
        form = AccountDeleteConfirmForm(user=request.user, confirmation_code=confirmation_code)
        context = {
            'form': form,
            'confirmation_code': confirmation_code,
            **self._get_data_counts(request.user),
        }
        return render(request, 'accounts/account_delete_confirm.html', context)

    def post(self, request):
        confirmation_code = self._get_confirmation_code(request)
        form = AccountDeleteConfirmForm(
            request.POST,
            user=request.user,
            confirmation_code=confirmation_code
        )
        if form.is_valid():
            # Clear the confirmation code from session
            if 'delete_confirmation_code' in request.session:
                del request.session['delete_confirmation_code']
            # Store email before deletion for the confirmation page
            deleted_email = request.user.email
            # Delete the user (cascades to games, leaderboards, scores)
            request.user.delete()
            logout(request)
            return render(request, 'accounts/account_deleted.html', {
                'deleted_email': deleted_email,
            })
        context = {
            'form': form,
            'confirmation_code': confirmation_code,
            **self._get_data_counts(request.user),
        }
        return render(request, 'accounts/account_delete_confirm.html', context)
