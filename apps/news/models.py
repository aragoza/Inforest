import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone
from decimal import Decimal

class News(models.Model):
    id_news = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    source = models.ForeignKey('core.Source', on_delete=models.CASCADE, related_name='news', verbose_name='source')
    country = models.ForeignKey('core.Country', on_delete=models.SET_NULL, null=True, blank=True, related_name='news', verbose_name='pays')
    title = models.CharField('titre', max_length=300)
    summary = models.TextField('résumé', blank=True)
    url = models.URLField('lien', max_length=1000, db_index=True)
    image_url = models.URLField('image', max_length=1000, blank=True)
    language = models.CharField('langue', max_length=5, blank=True)
    published_at = models.DateTimeField('date de publication', null=True, blank=True)
    fetched_at = models.DateTimeField('date de collecte', auto_now_add=True)

    hash = models.CharField('empreinte', max_length=40, unique=True)

    theme = models.CharField('thème', max_length=20, blank=True)
    status = models.BooleanField('validé', default=True, db_index=True)

    views = models.PositiveIntegerField('consultations', default=0)
    likes = models.PositiveIntegerField('mises en favori', default=0)
    rating = models.DecimalField('note', max_digits=3, decimal_places=2, default=0)

    class Meta:
        verbose_name = 'actualité'
        verbose_name_plural = 'actualités'
        ordering = ('-published_at', '-fetched_at')
        indexes = [
            models.Index(fields=['-published_at']),
            models.Index(fields=['country', '-published_at']),
        ]

    def __str__(self):
        return self.title

    def update_rating(self):
        if not self.views:
            self.rating = Decimal('0')
        else:
            note = Decimal(self.likes) / Decimal(self.views)
            self.rating = min(note, Decimal('1')).quantize(Decimal('0.01'))

        self.save(update_fields=['rating'])
        return self.rating



class UserNewsFavorite(models.Model):
    pk = models.CompositePrimaryKey('user_id', 'news_id')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='news_favorites', verbose_name='utilisateur')
    news = models.ForeignKey(News, on_delete=models.CASCADE, related_name='favorited_by', verbose_name='actualité')
    added_at = models.DateTimeField('ajouté le', auto_now_add=True)

    class Meta:
        verbose_name = 'favori (actualité)'
        verbose_name_plural = 'favoris (actualités)'
        ordering = ('-added_at',)


class UserNewsHistory(models.Model):
    pk = models.CompositePrimaryKey('user_id', 'news_id')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='news_history', verbose_name='utilisateur')
    news = models.ForeignKey(News, on_delete=models.CASCADE, related_name='read_by', verbose_name='actualité')
    viewed_at = models.DateTimeField('consulté le', default=timezone.now)

    class Meta:
        verbose_name = 'consultation (actualité)'
        verbose_name_plural = 'historique (actualités)'
        ordering = ('-viewed_at',)