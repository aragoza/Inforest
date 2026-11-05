"""Tests de l'application core : pays, sources et leurs commandes."""

from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from .feeds import FEEDS
from .models import MAX_FAILURES, Country, Source


class SourceHealthTests(TestCase):
    """Tests de la méthode mark_failure() et mark_success() de Source, qui gèrent le compteur d'échecs consécutifs et l'état actif/inactif (Booleen) de la source."""
    def setUp(self):
        self.source = Source.objects.create(name='S', feed_url='https://s.fr/feed', status=True)

    def test_echec_incremente_et_garde_lerreur(self):
        self.source.mark_failure('403 Forbidden')
        self.source.refresh_from_db()
        self.assertEqual(self.source.consecutive_failures, 1)
        self.assertEqual(self.source.last_error, '403 Forbidden')
        self.assertTrue(self.source.status)

    def test_desactivee_au_seuil(self):
        for _ in range(MAX_FAILURES):
            self.source.mark_failure('erreur')
        self.source.refresh_from_db()
        self.assertFalse(self.source.status)

    def test_encore_active_juste_avant_le_seuil(self):
        for _ in range(MAX_FAILURES - 1):
            self.source.mark_failure('erreur')
        self.source.refresh_from_db()
        self.assertTrue(self.source.status)

    def test_succes_efface_lhistorique_dechec(self):
        self.source.mark_failure('erreur')
        self.source.mark_success()
        self.source.refresh_from_db()
        self.assertEqual(self.source.consecutive_failures, 0)
        self.assertEqual(self.source.last_error, '')

    def test_message_derreur_tronque(self):
        self.source.mark_failure('x' * 5000)
        self.source.refresh_from_db()
        self.assertEqual(len(self.source.last_error), 1000)


class CountryTermsTests(TestCase):
    """Tests de la méthode match_terms() de Country, qui retourne les noms et mots-clés du pays pour la recherche d'articles."""

    def test_noms_officiels_et_termes_ajoutes(self):
        pays = Country(iso_code='CD', name='Congo', name_en='Congo',
                       keywords='RDC\n  Kinshasa  \n\n')
        termes = dict(pays.match_terms())
        self.assertIn('Congo', termes)
        self.assertIn('RDC', termes)
        self.assertIn('Kinshasa', termes)      # espaces retirés
        self.assertNotIn('', termes)           # lignes vides ignorées

    def test_termes_saisis_acceptent_une_longueur_plus_courte(self):
        termes = dict(Country(iso_code='CD', name='Congo', keywords='RDC').match_terms())
        self.assertLess(termes['RDC'], termes['Congo'])


class SeedCommandsTests(TestCase):
    """Tests des commandes seed_sources et seed_countries, qui créent les sources et pays de base."""

    def run_command(self, *args):
        out = StringIO()
        call_command(*args, stdout=out)
        return out.getvalue()

    def test_seed_sources_cree_inactives_par_defaut(self):
        self.run_command('seed_sources')
        self.assertEqual(Source.objects.count(), len(FEEDS))
        self.assertFalse(Source.objects.filter(status=True).exists())

    def test_seed_sources_actives(self):
        self.run_command('seed_sources', '--active')
        self.assertEqual(Source.objects.filter(status=True).count(), len(FEEDS))

    def test_seed_sources_idempotente(self):
        self.run_command('seed_sources')
        out = self.run_command('seed_sources')
        self.assertIn('0 source(s) créée(s)', out)
        self.assertEqual(Source.objects.count(), len(FEEDS))

    def test_seed_sources_ne_reactive_pas_une_source_coupee(self):
        # Relancer la commande ne doit pas écraser une décision prise
        # dans l'administration.
        self.run_command('seed_sources', '--active')
        Source.objects.update(status=False)
        self.run_command('seed_sources', '--active')
        self.assertFalse(Source.objects.filter(status=True).exists())

    def test_seed_countries_complet_et_en_francais(self):
        self.run_command('seed_countries')
        self.assertGreater(Country.objects.count(), 240)
        self.assertEqual(Country.objects.get(iso_code='DE').name, 'Allemagne')

    def test_seed_countries_conserve_les_termes_saisis(self):
        self.run_command('seed_countries')
        Country.objects.filter(iso_code='CD').update(keywords='RDC')
        self.run_command('seed_countries')
        self.assertEqual(Country.objects.get(iso_code='CD').keywords, 'RDC')


class AdminQueriesTests(TestCase):
    """Tests de l'administration Django pour les modèles Source et Country, 
    afin de vérifier que la liste des objets ne fait pas une requête par ligne affichée.
    Le nombre d'actualités par source vient d'une annotation : la liste ne
    doit pas faire une requête de plus par ligne affichée."""

    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_superuser(
            email='admin@exemple.fr', password='mot-de-passe-solide', name='Admin')

    def count_queries(self, url):
        self.client.force_login(self.admin)
        with CaptureQueriesContext(connection) as ctx:
            response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        return len(ctx.captured_queries)

    def test_liste_des_sources_sans_requete_par_ligne(self):
        url = reverse('admin:core_source_changelist')
        for i in range(2):
            Source.objects.create(name=f'S{i}', feed_url=f'https://s{i}.fr/feed')
        avec_deux = self.count_queries(url)

        for i in range(2, 20):
            Source.objects.create(name=f'S{i}', feed_url=f'https://s{i}.fr/feed')
        avec_vingt = self.count_queries(url)

        self.assertEqual(avec_deux, avec_vingt)

    def test_liste_des_pays_sans_requete_par_ligne(self):
        url = reverse('admin:core_country_changelist')
        Country.objects.create(iso_code='AA', name='A')
        avec_un = self.count_queries(url)

        for i in range(20):
            Country.objects.create(iso_code=f'{chr(66 + i)}X', name=f'P{i}')
        avec_vingt_et_un = self.count_queries(url)

        self.assertEqual(avec_un, avec_vingt_et_un)