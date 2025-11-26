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
