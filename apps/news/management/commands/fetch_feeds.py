from django.core.management.base import BaseCommand, CommandError

from apps.core.models import Source
from apps.news.services import fetch_all, fetch_source


class Command(BaseCommand):
    help = "Collecte les flux RSS actifs et enregistre les nouveaux articles."

    def add_arguments(self, parser):
        parser.add_argument('--all', action='store_true', help="Ne pas filtrer sur les mots-clés forestiers.")
        parser.add_argument('--source', help="Identifiant (UUID) d'une seule source.")

    def handle(self, *args, **options):
        only_forests = not options['all']

        if options['source']:
            try:
                source = Source.objects.get(pk=options['source'])
            except (Source.DoesNotExist, ValueError):
                raise CommandError(f"Aucune source d'identifiant {options['source']}.")

            counts = fetch_source(source, only_forests)
            report = [{
                'source': source,
                'created': counts['created'],
                'skipped': counts['skipped'],
                'has_failed': source.consecutive_failures > 0,
            }]
        else:
            report = fetch_all(only_forests)

        if not report:
            self.stdout.write(self.style.WARNING("Aucune source active. Ajoutez-en une dans l'administration."))
            return

        total_created = 0

        for line in report:
            source = line['source']

            if line['has_failed']:
                self.stdout.write(self.style.ERROR(
                    f'ECHEC  {source.name} : {source.last_error[:120]} '
                    f'({source.consecutive_failures} échec(s) consécutif(s))')
                    )
                continue

            total_created += line['created']
            self.stdout.write(self.style.SUCCESS(
                f"OK {source.name} : {line['created']} nouveau(x), "
                f"{line['skipped']} ignoré(s)")
                )

        self.stdout.write(self.style.MIGRATE_HEADING(f'\n{total_created} article(s) ajouté(s) en base.'))