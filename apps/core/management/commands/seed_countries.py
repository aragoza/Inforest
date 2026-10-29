import gettext
import pycountry
from django.core.management.base import BaseCommand
from apps.core.models import Country

class Command(BaseCommand):
    def handle(self, *args, **options):
        traduction = gettext.translation('iso3166-1', pycountry.LOCALES_DIR, languages=['fr'])

        avant = Country.objects.count()

        for pays in pycountry.countries:
            Country.objects.update_or_create(
                iso_code=pays.alpha_2,
                defaults={
                    'name': traduction.gettext(pays.name),
                    'name_en': pays.name,
                },
            )

        total = Country.objects.count()