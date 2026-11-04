"""Composition et envoi du mail hebdomadaire.

La logique vit ici, pas dans la commande ni dans la tâche : les deux
l'appellent, et elle reste testable sans réseau ni ordonnanceur.
"""

from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import EmailMultiAlternatives, get_connection
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from apps.news.models import News

User = get_user_model()

ARTICLES_PER_MAIL = 5
DAYS_COVERED = 7

# Limite de mail journalier de resend
MAX_PER_RUN = 100

# Une limite de 6 jours entre deux envois pour un même utilisateur
MIN_DAYS_BETWEEN = 6


def weekly_articles(user, limit=ARTICLES_PER_MAIL, days=DAYS_COVERED):
    """Articles de la semaine : son pays d'abord, le monde en complément."""
    since = timezone.now() - timedelta(days=days)

    published = (News.objects
             .filter(status=True, published_at__gte=since)
             .select_related('source', 'country'))

    articles = []

    if user.country_id:
        articles = list(published.filter(country_id=user.country_id)[:limit])

    if len(articles) < limit:
        already_chosen = [article.pk for article in articles]
        complement = published.exclude(pk__in=already_chosen)[:limit - len(articles)]
        articles += list(complement)

    return articles


def unsubscribe_url(user):
    path = reverse('accounts:newsletter_unsubscribe', args=[user.newsletter_token])
    return settings.SITE_URL + path


def build_message(user, articles, connection=None):
    """Prépare le message d'un abonné, sans l'envoyer."""
    context = {
        'user': user,
        'articles': articles,
        'unsubscribe_url': unsubscribe_url(user),
        'site_url': settings.SITE_URL,
    }

    message = EmailMultiAlternatives(
        subject='InForêt — les forêts cette semaine',
        body=render_to_string('emails/weekly.txt', context),
        to=[user.email],
        connection=connection,
        # Permet aux messageries d'afficher leur propre bouton de désinscription.
        headers={
            'List-Unsubscribe': f'<{context["unsubscribe_url"]}>',
            'List-Unsubscribe-Post': 'List-Unsubscribe=One-Click',
        },
    )
    message.attach_alternative(render_to_string('emails/weekly.html', context), 'text/html')
    return message


def send_weekly(dry_run=False, max_per_run=MAX_PER_RUN):
    """Envoie le mail à tous les abonnés. Renvoie un compte-rendu."""
    recently = timezone.now() - timedelta(days=MIN_DAYS_BETWEEN)

    subscribers = (User.objects
                   .filter(newsletter_option=True, is_active=True)
                   .exclude(last_newsletter_sent_at__gt=recently)
                   .select_related('country')
                   .order_by('last_newsletter_sent_at'))

    total_subscribers = subscribers.count()
    sent = 0
    without_articles = 0

    # Une seule connexion SMTP pour tout le lot, au lieu d'une par message.
    connection = get_connection()

    for user in subscribers[:max_per_run]:
        articles = weekly_articles(user)

        if not articles:
            without_articles += 1
            continue

        if dry_run:
            sent += 1
            continue

        build_message(user, articles, connection).send()

        user.last_newsletter_sent_at = timezone.now()
        user.save(update_fields=['last_newsletter_sent_at'])
        sent += 1

    return {
        'subscribers': total_subscribers,
        'sent': sent,
        'without_articles': without_articles,
        'postponed': max(total_subscribers - max_per_run, 0),
    }