from django.contrib import admin

from .models import News


@admin.register(News)
class NewsAdmin(admin.ModelAdmin):
    list_display = ('title', 'source', 'country', 'published_at', 'views', 'likes', 'status')
    list_filter = ('status', 'source', 'country', 'language')
    search_fields = ('title', 'summary', 'url')
    date_hierarchy = 'published_at'
    readonly_fields = ('source', 'country', 'title', 'summary', 'url', 'image_url', 'language', 'published_at', 'fetched_at', 'hash', 'views', 'likes', 'rating')
    actions = ('valider',)

    def has_add_permission(self, request):
        return False

    @admin.action(description='Valider les actualités sélectionnées')
    def valider(self, request, queryset):
        n = queryset.update(status=True)
        self.message_user(request, f'{n} actualité(s) validée(s).')