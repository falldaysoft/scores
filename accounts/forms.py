from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import User


class SignupForm(UserCreationForm):
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent',
            'placeholder': 'you@example.com'
        })
    )
    account_name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent',
            'placeholder': 'Your studio or developer name'
        })
    )
    password1 = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent',
            'placeholder': 'Password'
        })
    )
    password2 = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent',
            'placeholder': 'Confirm password'
        })
    )

    class Meta:
        model = User
        fields = ['email', 'account_name', 'password1', 'password2']

    def clean_account_name(self):
        account_name = self.cleaned_data.get('account_name')
        if account_name:
            account_name = account_name.strip()
            if not account_name:
                raise forms.ValidationError('Account name is required.')
            existing = User.objects.filter(account_name__iexact=account_name)
            if existing.exists():
                raise forms.ValidationError('This account name is already taken.')
        return account_name


class LoginForm(AuthenticationForm):
    username = forms.EmailField(
        label='Email',
        widget=forms.EmailInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent',
            'placeholder': 'you@example.com'
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent',
            'placeholder': 'Password'
        })
    )


class AccountSettingsForm(forms.ModelForm):
    account_name = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent',
            'placeholder': 'Your account name'
        })
    )

    class Meta:
        model = User
        fields = ['account_name']

    def clean_account_name(self):
        account_name = self.cleaned_data.get('account_name')
        if account_name:
            account_name = account_name.strip()
            if not account_name:
                return None
            existing = User.objects.filter(account_name__iexact=account_name).exclude(pk=self.instance.pk)
            if existing.exists():
                raise forms.ValidationError('This account name is already taken.')
        else:
            return None
        return account_name


class AccountDeleteConfirmForm(forms.Form):
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent',
            'placeholder': 'Enter your password',
            'autocomplete': 'current-password',
        })
    )
    confirmation = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent',
            'autocomplete': 'off',
        })
    )

    def __init__(self, *args, user=None, confirmation_code=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.confirmation_code = confirmation_code
        if confirmation_code:
            self.fields['confirmation'].widget.attrs['placeholder'] = f'Type {confirmation_code} to confirm'

    def clean_password(self):
        password = self.cleaned_data.get('password')
        if self.user and not self.user.check_password(password):
            raise forms.ValidationError('Incorrect password.')
        return password

    def clean_confirmation(self):
        confirmation = self.cleaned_data.get('confirmation')
        if confirmation != self.confirmation_code:
            raise forms.ValidationError(f'Please type "{self.confirmation_code}" exactly to confirm deletion.')
        return confirmation
