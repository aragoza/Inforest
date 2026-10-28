from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.forms import UserCreationForm

from .models import User


class RegisterForm(UserCreationForm):
    class Meta:
        model = User
        fields = ('name', 'email', 'newsletter_option')
        labels = {
            'name': 'Nom affiché',
            'email': 'Adresse email',
            'newsletter_option': 'Je souhaite recevoir le récapitulatif hebdomadaire',
        }

    def clean_email(self):
        email = self.cleaned_data['email'].lower()
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("Un compte existe déjà avec cette adresse.")
        return email


class LoginForm(forms.Form):
    email = forms.EmailField(label='Adresse email')
    password = forms.CharField(
        label='Mot de passe',
        strip=False,
        widget=forms.PasswordInput,
    )

    def __init__(self, request=None, *args, **kwargs):
        self.request = request
        self.user = None
        super().__init__(*args, **kwargs)

    def clean(self):
        email = self.cleaned_data.get('email')
        password = self.cleaned_data.get('password')

        if email and password:
            self.user = authenticate(self.request, email=email, password=password)
            if self.user is None:
                raise forms.ValidationError("Adresse email ou mot de passe incorrect.")

        return self.cleaned_data

    def get_user(self):
        return self.user


class PreferencesForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ('name', 'country', 'newsletter_option')
        labels = {
            'name': 'Nom affiché',
            'country': 'Pays suivi',
            'newsletter_option': 'Recevoir le récapitulatif hebdomadaire',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['country'].empty_label = 'Aucun (actualité mondiale)'

class DeleteAccountForm(forms.Form):
    password = forms.CharField(
        label='Confirmez avec votre mot de passe',
        strip=False,
        widget=forms.PasswordInput,
    )
    confirm = forms.BooleanField(
        label="Je comprends que la suppression est définitive et immédiate",
    )

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_password(self):
        password = self.cleaned_data['password']
        if not self.user.check_password(password):
            raise forms.ValidationError("Mot de passe incorrect.")
        return password