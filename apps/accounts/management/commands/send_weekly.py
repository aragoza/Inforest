from django.core.management.base import BaseCommand

from apps.accounts.newsletter import send_weekly


class Command(BaseCommand):
    help = 'Envoie le mail hebdomadaire aux abonnés.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help="Compte les destinataires sans rien envoyer.")

    def handle(self, *args, **options):
        report = send_weekly(dry_run=options['dry_run'])

        if options['dry_run']:
            self.stdout.write('Essai à blanc : aucun mail envoyé.')

        self.stdout.write(
            f"{report['subscribers']} abonné(s), {report['sent']} envoi(s), "
            f"{report['without_articles']} sans article, "
            f"{report['postponed']} reporté(s) au prochain lot.")