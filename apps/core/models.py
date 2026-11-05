import uuid

from django.db import models
from django.utils import timezone

class Country(models.Model):
    id_country = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    iso_code = models.CharField('code ISO', max_length=2, unique=True)
    name = models.CharField('nom', max_length=100)
    name_en = models.CharField('nom anglais', max_length=100, blank=True)
    keywords = models.TextField('mots-clés', blank=True)

    class Meta:
        verbose_name = 'pays'
        verbose_name_plural = 'pays'
        ordering = ('name',)

    def __str__(self):
        return self.name

    def match_terms(self):
        termes = [(t, 4) for t in (self.name, self.name_en) if t]
        termes += [(ligne.strip(), 3) for ligne in self.keywords.splitlines()
                   if ligne.strip()]
        return termes


# Au-delà de ce nombre d'échecs consécutifs, la source se désactive d'elle-même.
MAX_FAILURES = 5

class Source(models.Model):
    id_source = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    name = models.CharField('nom', max_length=120)
    feed_url = models.URLField('URL du flux', max_length=500, unique=True)
    site_url = models.URLField('URL du site', max_length=500, blank=True)
    language = models.CharField('langue', max_length=5, default='fr')
    status = models.BooleanField('activé', default=False)
    created_at = models.DateTimeField("date d'ajout", auto_now_add=True)

    last_fetch_at = models.DateTimeField('dernière collecte', null=True, blank=True)
    last_error = models.TextField('dernière erreur', blank=True)
    consecutive_failures = models.PositiveIntegerField('échecs consécutifs', default=0)

    for_news = models.BooleanField('alimente les actualités', default=True)
    for_discovery = models.BooleanField('alimente les découvertes', default=False)

    class Meta:
        verbose_name = 'source'
        verbose_name_plural = 'sources'
        ordering = ('name',)

    def __str__(self):
        return self.name

    def mark_success(self):
        self.last_fetch_at = timezone.now()
        self.last_error = ''
        self.consecutive_failures = 0
        self.save(update_fields=['last_fetch_at', 'last_error', 'consecutive_failures'])

    def mark_failure(self, message):
        self.last_fetch_at = timezone.now()
        self.last_error = str(message)[:1000]
        self.consecutive_failures += 1

        if self.consecutive_failures >= MAX_FAILURES:
            self.status = False

        self.save(update_fields=['last_fetch_at', 'last_error', 'consecutive_failures', 'status'])
