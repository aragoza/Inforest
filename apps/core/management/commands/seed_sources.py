"""Insère les flux dans la table Source"""

from django.core.management.base import BaseCommand

from apps.core.feeds import FEEDS
from apps.core.models import Source


class Command(BaseCommand):
    help = "Insère les flux dans la table Source."

    def add_arguments(self, parser):
        parser.add_argument('--active', action='store_true', help="Créer les sources directement actives.")

    def handle(self, *args, **options):
        is_active = bool(options['active'])
        before = Source.objects.count()

        for name, feed_url, language, for_news, for_discovery in FEEDS:
            Source.objects.get_or_create(
                feed_url=feed_url,
                defaults={
                    'name': name,
                    'language': language,
                    'status': is_active,
                    'for_news': for_news,
                    'for_discovery': for_discovery,
                },
            )

        total = Source.objects.count()
        self.stdout.write(self.style.SUCCESS(
            f'{total - before} source(s) créée(s). Total en base : {total}.'))

        if not is_active:
            self.stdout.write(
                "Les sources sont inactives : activez-les depuis l'administration, "
                "ou relancez avec --active.")