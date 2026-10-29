from django.contrib import admin
from django.db.models import Count

from .models import Country, Source


@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
    list_display = ('name', 'iso_code', 'name_en', 'news_count')
    search_fields = ('name', 'name_en', 'iso_code', 'keywords')

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_news_count=Count('news'))

    @admin.display(description='actualités', ordering='_news_count')
    def news_count(self, country):
        return country._news_count


@admin.register(Source)
class SourceAdmin(admin.ModelAdmin):
    list_display = ('name', 'status', 'for_news', 'for_discovery', 'language', 'news_count', 'last_fetch_at', 'consecutive_failures')
    list_filter = ('status', 'for_news', 'for_discovery', 'language')
    search_fields = ('name', 'feed_url')
    readonly_fields = ('last_fetch_at', 'last_error', 'consecutive_failures', 'created_at')
    actions = ('activer', 'desactiver')

    fieldsets = (
        (None, {'fields': ('name', 'feed_url', 'site_url', 'language')}),
        ('Utilisation', {'fields': ('status', 'for_news', 'for_discovery')}),
        ('État du flux', {'fields': ('last_fetch_at', 'consecutive_failures', 'last_error', 'created_at')}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_news_count=Count('news'))

    @admin.display(description='actualités', ordering='_news_count')
    def news_count(self, source):
        return source._news_count

    @admin.action(description='Activer les sources sélectionnées')
    def activer(self, request, queryset):
        n = queryset.update(status=True, consecutive_failures=0)
        self.message_user(request, f'{n} source(s) activée(s).')

    @admin.action(description='Désactiver les sources sélectionnées')
    def desactiver(self, request, queryset):
        n = queryset.update(status=False)
        self.message_user(request, f'{n} source(s) désactivée(s).')