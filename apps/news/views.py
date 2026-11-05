from django.contrib.auth.decorators import login_required
from django.db.models import Case, IntegerField, When
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.models import Source

from .models import News, UserNewsFavorite, UserNewsHistory

MAX_ARTICLES = 60


def news_list(request):
    """Liste des actualités, avec le pays suivi en tête pour un connecté"""
    news = (News.objects
            .filter(status=True)
            .select_related('source', 'country'))

    query = request.GET.get('q', '').strip()
    if query:
        in_title = news.filter(title__icontains=query)
        in_summary = news.filter(summary__icontains=query)
        news = in_title | in_summary

    source_id = request.GET.get('source', '')
    if source_id:
        news = news.filter(source_id=source_id)

    followed_country_id = None
    if request.user.is_authenticated:
        followed_country_id = request.user.country_id

    if followed_country_id:
        news = news.annotate(
            priority=Case(
                When(country_id=followed_country_id, then=0),
                default=1,
                output_field=IntegerField(),
            )
        ).order_by('priority', '-published_at', '-fetched_at')

    favorite_ids = set()
    if request.user.is_authenticated:
        favorite_ids = set(UserNewsFavorite.objects
                           .filter(user=request.user)
                           .values_list('news_id', flat=True))

    followed_country = None
    if followed_country_id:
        followed_country = request.user.country

    return render(request, 'news/list.html', {
        'news': news[:MAX_ARTICLES],
        'query': query,
        'sources': Source.objects.filter(status=True, for_news=True),
        'current_source': source_id,
        'followed_country': followed_country,
        'favorite_ids': favorite_ids,
    })


def news_detail(request, pk):
    """Fiche d'un article"""
    article = get_object_or_404(News.objects.select_related('source', 'country'), pk=pk)

    is_favorite = False
    if request.user.is_authenticated:
        is_favorite = UserNewsFavorite.objects.filter(
            user=request.user, news=article).exists()

    return render(request, 'news/detail.html', {
        'new': article,
        'is_favorite': is_favorite,
    })


def news_read(request, pk):
    """Compte la consultation, note l'historique, puis redirige vers l'article d'origine"""
    article = get_object_or_404(News, pk=pk)

    article.views += 1
    article.save(update_fields=['views'])

    if request.user.is_authenticated:
        UserNewsHistory.objects.update_or_create(
            user=request.user,
            news=article,
            defaults={'viewed_at': timezone.now()},
        )

    article.update_rating()

    return redirect(article.url)


@require_POST
@login_required
def toggle_favorite(request, pk):
    """Ajoute ou retire un favori"""
    article = get_object_or_404(News, pk=pk)

    favorite, created = UserNewsFavorite.objects.get_or_create(
        user=request.user, news=article)

    if not created:
        favorite.delete()

    article.likes = article.favorited_by.count()
    article.save(update_fields=['likes'])
    article.update_rating()

    return redirect('news:detail', pk=article.pk)


@login_required
def favorites(request):
    news = (News.objects
            .filter(favorited_by__user=request.user)
            .select_related('source', 'country')
            .order_by('-favorited_by__added_at'))

    return render(request, 'news/favorites.html', {'news': news})


@login_required
def history(request):
    news = (News.objects
            .filter(read_by__user=request.user)
            .select_related('source', 'country')
            .order_by('-read_by__viewed_at'))

    return render(request, 'news/history.html', {'news': news})