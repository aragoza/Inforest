from django.db.models import Case, IntegerField, When
from django.shortcuts import render
from django.utils import timezone

from apps.discovery.views import DISCOVERIES, THEMES
from apps.maps.views import LAYERS
from apps.news.models import News

# Nombre d'actualités affichées sur la page d'accueil.
HOME_ARTICLES = 5


def daily_discovery():
    """Choisit une découverte qui change chaque jour et reste la même toute la journée"""
    day_number = timezone.localdate().toordinal()
    position = day_number % len(DISCOVERIES)
    return DISCOVERIES[position]


def home(request):
    """Page d'accueil : dernières actualités, découverte du jour et accès à la carte"""
    news = (News.objects
            .filter(status=True)
            .select_related('source', 'country'))

    followed_country = None
    if request.user.is_authenticated and request.user.country_id:
        followed_country = request.user.country
        news = news.annotate(
            priority=Case(
                When(country_id=request.user.country_id, then=0),
                default=1,
                output_field=IntegerField(),
            )
        ).order_by('priority', '-published_at', '-fetched_at')

    discovery = daily_discovery()
    theme_label = dict(THEMES).get(discovery['theme'])

    return render(request, 'home.html', {
        'news': news[:HOME_ARTICLES],
        'followed_country': followed_country,
        'discovery': discovery,
        'theme_label': theme_label,
        'layers': LAYERS,
    })