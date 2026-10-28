from django.contrib import messages
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.http import JsonResponse

from .forms import DeleteAccountForm, LoginForm, PreferencesForm, RegisterForm


def register(request):
    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Bienvenue, votre compte est créé.')
            return redirect('home')
    else:
        form = RegisterForm()

    return render(request, 'accounts/register.html', {'form': form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            login(request, form.get_user())
            return redirect('home')
    else:
        form = LoginForm(request)

    return render(request, 'accounts/login.html', {'form': form})


@require_POST
def logout_view(request):
    logout(request)
    messages.info(request, 'Vous êtes déconnecté.')
    return redirect('home')


@login_required
def profile(request):
    return render(request, 'accounts/profile.html')


@login_required
def preferences(request):
    if request.method == 'POST':
        form = PreferencesForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Vos préférences sont enregistrées.')
            return redirect('accounts:profile')
    else:
        form = PreferencesForm(instance=request.user)

    return render(request, 'accounts/preferences.html', {'form': form})


@login_required
def change_password(request):
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)  # évite la déconnexion après changement
            messages.success(request, 'Votre mot de passe a été modifié.')
            return redirect('accounts:profile')
    else:
        form = PasswordChangeForm(request.user)

    return render(request, 'accounts/change_password.html', {'form': form})


@login_required
def delete_account(request):
    if request.method == 'POST':
        form = DeleteAccountForm(request.user, request.POST)
        if form.is_valid():
            user = request.user
            logout(request)
            user.delete()
            messages.success(request, 'Votre compte et vos données ont été supprimés.')
            return redirect('home')
    else:
        form = DeleteAccountForm(request.user)

    return render(request, 'accounts/delete_account.html', {'form': form})

@login_required
def export_data(request):
    user = request.user

    payload = {
        'exported_at': timezone.now().isoformat(),
        'account': {
            'name': user.name,
            'email': user.email,
            'country': user.country.name if user.country else None,
            'newsletter_option': user.newsletter_option,
            'created_at': user.created_at.isoformat(),
            'last_login': user.last_login.isoformat() if user.last_login else None,
        },
        'favorites': [
            {'title': f.news.title, 'url': f.news.url,
             'added_at': f.added_at.isoformat()}
            for f in user.news_favorites.select_related('news')
        ],
        'history': [
            {'title': h.news.title, 'url': h.news.url,
             'viewed_at': h.viewed_at.isoformat()}
            for h in user.news_history.select_related('news')
        ],
    }

    response = JsonResponse(payload, json_dumps_params={'ensure_ascii': False, 'indent': 2})
    response['Content-Disposition'] = 'attachment; filename="mes-donnees.json"'
    return response