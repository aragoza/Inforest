"""Tests de l'application news.

Trois niveaux, du plus rapide au plus large :
- les fonctions pures du pipeline (normalisation, empreinte, validation,
  pertinence, pays), sans base ni réseau ;
- l'enregistrement et la collecte, avec la base de test et un réseau simulé ;
- les vues, avec le client de test de Django.

Aucun test n'appelle Internet : un test qui dépend d'un site extérieur échoue
le jour où ce site change, sans que le projet ait changé.
"""

import unittest
from datetime import UTC, datetime
from unittest import mock

import feedparser
import requests
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils.text import slugify

from apps.core.models import MAX_FAILURES, Country, Source

from .models import News, UserNewsFavorite, UserNewsHistory
from .services import (
    build_country_terms,
    detect_country,
    fetch_source,
    is_about_forests,
    make_hash,
    normalize_text,
    normalize_url,
    save_entries,
    shorten,
    strip_html,
    validate_feed,
)

User = get_user_model()


# --------------------------------------------------------------------------
# Flux d'exemple
# --------------------------------------------------------------------------

RSS = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
  <title>Exemple RSS</title>
  <item>
    <title>La deforestation recule en Amazonie</title>
    <link>https://exemple.fr/amazonie?utm_source=rss</link>
    <description>&lt;p&gt;Un recul de la deforestation au Bresil.&lt;/p&gt;</description>
    <pubDate>Mon, 02 Nov 2026 08:00:00 GMT</pubDate>
  </item>
  <item>
    <title>Le prix du cafe augmente</title>
    <link>https://exemple.fr/cafe</link>
    <description>Les cours mondiaux montent encore.</description>
  </item>
</channel></rss>"""

ATOM = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Exemple Atom</title>
  <entry>
    <title>Reboisement dans les Vosges</title>
    <link href="https://exemple.fr/vosges"/>
    <summary>Un programme de reboisement.</summary>
    <updated>2026-11-02T08:00:00Z</updated>
  </entry>
</feed>"""

PAS_UN_FLUX = b"<html><body>Page d'accueil</body></html>"

FLUX_VIDE = b"""<?xml version="1.0"?><rss version="2.0"><channel>
<title>Vide</title></channel></rss>"""


def make_source(**extra):
    values = {'name': 'Exemple', 'feed_url': 'https://exemple.fr/feed', 'status': True}
    values.update(extra)
    return Source.objects.create(**values)


def make_news(source, title='La foret recule', **extra):
    values = {
        'source': source,
        'title': title,
        'url': 'https://exemple.fr/' + slugify(title),
        'hash': make_hash(title, 'https://exemple.fr/' + slugify(title)),
        'published_at': datetime(2026, 11, 2, 8, tzinfo=UTC),
    }
    values.update(extra)
    return News.objects.create(**values)


# --------------------------------------------------------------------------
# Fonctions de texte et d'URL
# --------------------------------------------------------------------------

class TextToolsTests(unittest.TestCase):
    """Tests des fonctions de normalisation et de résumé de texte, sans base ni réseau."""

    def test_normalize_text_retire_accents_et_majuscules(self):
        self.assertEqual(normalize_text('Forêt ÉQUATORIALE'), 'foret equatoriale')

    def test_normalize_text_supporte_none(self):
        self.assertEqual(normalize_text(None), '')

    def test_strip_html_retire_balises_et_espaces(self):
        self.assertEqual(strip_html('<p>Un   <b>arbre</b>\n</p>'), 'Un arbre')

    def test_shorten_coupe_sur_un_espace(self):
        result = shorten('un deux trois quatre', limit=10)
        self.assertEqual(result, 'un deux…')

    def test_shorten_ne_touche_pas_un_texte_court(self):
        self.assertEqual(shorten('court', limit=10), 'court')


class NormalizeUrlTests(unittest.TestCase):
    """Sans base de données : unittest.TestCase suffit et va plus vite."""

    def test_retire_les_parametres_de_suivi(self):
        self.assertEqual(
            normalize_url('https://exemple.fr/a?utm_source=x&id=4&fbclid=y'),
            'https://exemple.fr/a?id=4')

    def test_domaine_en_minuscules_et_slash_final_retire(self):
        self.assertEqual(normalize_url('HTTPS://Exemple.FR/Article/'),
                         'https://exemple.fr/Article')

    def test_le_chemin_garde_sa_casse(self):
        # Un chemin est sensible à la casse côté serveur : le modifier
        # pourrait mener à une autre page.
        self.assertIn('/Article', normalize_url('https://exemple.fr/Article'))


class MakeHashTests(unittest.TestCase):
    """Sans base de données : unittest.TestCase suffit et va plus vite."""
    def test_quatre_formes_dun_meme_article_donnent_une_empreinte(self):
        formes = [
            'https://exemple.fr/article',
            'https://exemple.fr/article/',
            'https://EXEMPLE.fr/article?utm_source=newsletter',
            'https://exemple.fr/article?fbclid=abc&utm_medium=social',
        ]
        empreintes = {make_hash('La forêt recule', url) for url in formes}
        self.assertEqual(len(empreintes), 1)

    def test_titre_insensible_aux_accents_et_a_la_casse(self):
        self.assertEqual(make_hash('La Forêt', 'https://exemple.fr/a'),
                         make_hash('la foret', 'https://exemple.fr/a'))

    def test_deux_articles_differents_ne_se_confondent_pas(self):
        self.assertNotEqual(make_hash('Article A', 'https://exemple.fr/a'),
                            make_hash('Article B', 'https://exemple.fr/b'))

    def test_longueur_compatible_avec_le_champ(self):
        self.assertEqual(len(make_hash('t', 'https://exemple.fr')), 40)


# --------------------------------------------------------------------------
# Validation d'un flux
# --------------------------------------------------------------------------

class ValidateFeedTests(unittest.TestCase):
    """Test de la fonction validate_feed() qui analyse un flux RSS ou Atom."""

    def test_rss_valide(self):
        self.assertTrue(validate_feed(feedparser.parse(RSS))['is_valid'])

    def test_atom_valide(self):
        # Les deux normes doivent passer : c'est tout l'intérêt de normaliser.
        self.assertTrue(validate_feed(feedparser.parse(ATOM))['is_valid'])

    def test_une_page_html_est_refusee(self):
        result = validate_feed(feedparser.parse(PAS_UN_FLUX))
        self.assertFalse(result['is_valid'])
        self.assertIn("ce n'est pas un flux", result['problems'][0])

    def test_un_flux_vide_est_refuse_sans_division_par_zero(self):
        result = validate_feed(feedparser.parse(FLUX_VIDE))
        self.assertFalse(result['is_valid'])
        self.assertIn('aucune entrée', result['problems'][0])

    def test_trop_dentrees_sans_titre(self):
        items = ''.join(f'<item><link>https://e.fr/{i}</link></item>' for i in range(5))
        items += '<item><title>Seul titre</title><link>https://e.fr/x</link></item>'
        flux = f'<?xml version="1.0"?><rss version="2.0"><channel><title>t</title>{items}</channel></rss>'
        result = validate_feed(feedparser.parse(flux.encode()))
        self.assertFalse(result['is_valid'])
        self.assertIn('sans titre', result['problems'][0])


# --------------------------------------------------------------------------
# Pertinence et pays
# --------------------------------------------------------------------------

class IsAboutForestsTests(unittest.TestCase):
    """Tests de la fonction is_about_forests() qui filtre les articles pertinents."""

    def check(self, titre, resume=''):
        return is_about_forests({'title': titre, 'summary': resume})

    def test_titre_francais_accentue(self):
        self.assertTrue(self.check('La déforestation recule'))

    def test_titre_anglais(self):
        self.assertTrue(self.check('Rainforest loss slows in Brazil'))

    def test_mot_cle_dans_le_resume_seulement(self):
        self.assertTrue(self.check('Bonne nouvelle', 'un programme de reboisement'))

    def test_article_hors_sujet(self):
        self.assertFalse(self.check('Le prix du café augmente'))

    # Limite connue : la comparaison se fait par inclusion de chaîne. « bois »
    # est trouvé dans « boissons », « tree » dans « street ». Ces tests décrivent
    # le comportement attendu ; ils sont marqués comme échecs attendus tant que
    # le filtre n'est pas corrigé. Le jour où il l'est, unittest signale une
    # « réussite inattendue » : il faudra alors retirer le décorateur.

    @unittest.expectedFailure
    def test_boissons_ne_parle_pas_de_bois(self):
        self.assertFalse(self.check('Hausse du prix des boissons sucrées'))

    @unittest.expectedFailure
    def test_street_ne_parle_pas_darbres(self):
        self.assertFalse(self.check('Street art : une fresque géante'))


class DetectCountryTests(TestCase):
    """Tests de la fonction detect_country() qui reconnaît le pays d'un article."""

    @classmethod
    def setUpTestData(cls):
        cls.guinee = Country.objects.create(iso_code='GN', name='Guinée')
        cls.guinee_eq = Country.objects.create(iso_code='GQ', name='Guinée équatoriale')
        cls.france = Country.objects.create(iso_code='FR', name='France', name_en='France')
        cls.rdc = Country.objects.create(iso_code='CD', name='Congo (RDC)',
                                         keywords='RDC\nKinshasa')

    def detect(self, titre):
        return detect_country({'title': titre, 'summary': ''}, build_country_terms())

    def test_le_terme_le_plus_long_lemporte(self):
        # Sans tri par longueur, « Guinée » serait trouvé en premier.
        self.assertEqual(self.detect('Forêts de Guinée équatoriale'), self.guinee_eq.pk)

    def test_mot_entier_seulement(self):
        self.assertIsNone(self.detect('Francesca plante des arbres'))

    def test_pays_cite(self):
        self.assertEqual(self.detect('Les forêts de France brûlent'), self.france.pk)

    def test_terme_saisi_dans_ladministration(self):
        # « RDC » fait trois lettres : il passe parce que les termes ajoutés
        # à la main acceptent une longueur minimale plus courte.
        self.assertEqual(self.detect('La RDC protège sa forêt'), self.rdc.pk)

    def test_aucun_pays(self):
        self.assertIsNone(self.detect('La forêt mondiale en chiffres'))


# --------------------------------------------------------------------------
# Enregistrement et collecte
# --------------------------------------------------------------------------

class SaveEntriesTests(TestCase):
    """Tests de la fonction save_entries() qui enregistre les articles dans la base."""

    @classmethod
    def setUpTestData(cls):
        cls.source = make_source()
        cls.bresil = Country.objects.create(iso_code='BR', name='Brésil', name_en='Brazil',
                                            keywords='Bresil')

    def test_enregistre_seulement_les_articles_pertinents(self):
        counts = save_entries(self.source, feedparser.parse(RSS).entries)
        self.assertEqual(counts, {'created': 1, 'skipped': 1})
        self.assertEqual(News.objects.get().title, 'La deforestation recule en Amazonie')

    def test_deuxieme_passage_ne_cree_aucun_doublon(self):
        entries = feedparser.parse(RSS).entries
        save_entries(self.source, entries)
        counts = save_entries(self.source, entries)
        self.assertEqual(counts['created'], 0)
        self.assertEqual(News.objects.count(), 1)

    def test_url_enregistree_sans_parametre_de_suivi(self):
        save_entries(self.source, feedparser.parse(RSS).entries)
        self.assertEqual(News.objects.get().url, 'https://exemple.fr/amazonie')

    def test_pays_reconnu_dans_le_resume(self):
        save_entries(self.source, feedparser.parse(RSS).entries)
        self.assertEqual(News.objects.get().country, self.bresil)

    def test_resume_sans_html(self):
        save_entries(self.source, feedparser.parse(RSS).entries)
        self.assertNotIn('<p>', News.objects.get().summary)

    def test_sans_filtre_tout_est_garde(self):
        counts = save_entries(self.source, feedparser.parse(RSS).entries, only_forests=False)
        self.assertEqual(counts['created'], 2)


def fake_response(content):
    response = mock.Mock()
    response.content = content
    response.raise_for_status = mock.Mock()
    return response


class FetchSourceTests(TestCase):
    """Tests de la fonction fetch_source() qui récupère un flux et l'enregistre.
    Le réseau est simulé : on remplace requests.get par un double.
    """

    def setUp(self):
        self.source = make_source()

    @mock.patch('apps.news.services.requests.get')
    def test_succes_remet_le_compteur_a_zero(self, get):
        self.source.consecutive_failures = 3
        self.source.save()
        get.return_value = fake_response(RSS)

        counts = fetch_source(self.source, country_terms=[])

        self.source.refresh_from_db()
        self.assertEqual(counts['created'], 1)
        self.assertEqual(self.source.consecutive_failures, 0)
        self.assertEqual(self.source.last_error, '')
        self.assertIsNotNone(self.source.last_fetch_at)

    @mock.patch('apps.news.services.requests.get')
    def test_erreur_reseau_comptee_sans_interrompre(self, get):
        get.side_effect = requests.ConnectionError('injoignable')

        counts = fetch_source(self.source, country_terms=[])

        self.source.refresh_from_db()
        self.assertEqual(counts, {'created': 0, 'skipped': 0})
        self.assertEqual(self.source.consecutive_failures, 1)
        self.assertIn('injoignable', self.source.last_error)

    @mock.patch('apps.news.services.requests.get')
    def test_flux_invalide_compte_comme_un_echec(self, get):
        get.return_value = fake_response(PAS_UN_FLUX)

        fetch_source(self.source, country_terms=[])

        self.source.refresh_from_db()
        self.assertEqual(self.source.consecutive_failures, 1)
        self.assertIn('inexploitable', self.source.last_error)

    @mock.patch('apps.news.services.requests.get')
    def test_desactivation_automatique_apres_trop_dechecs(self, get):
        get.side_effect = requests.Timeout('trop lent')

        for _ in range(MAX_FAILURES):
            fetch_source(self.source, country_terms=[])

        self.source.refresh_from_db()
        self.assertFalse(self.source.status)
        self.assertEqual(self.source.consecutive_failures, MAX_FAILURES)


# --------------------------------------------------------------------------
# Vues
# --------------------------------------------------------------------------

class NewsViewsTests(TestCase):
    """Tests des vues de l'application news, avec base de test et client Django."""

    @classmethod
    def setUpTestData(cls):
        cls.source = make_source()
        cls.france = Country.objects.create(iso_code='FR', name='France')
        cls.bresil = Country.objects.create(iso_code='BR', name='Brésil')

        cls.article_monde = make_news(
            cls.source, 'Article mondial récent',
            published_at=datetime(2026, 11, 3, tzinfo=UTC))
        cls.article_france = make_news(
            cls.source, 'Article français ancien', country=cls.france,
            published_at=datetime(2026, 10, 1, tzinfo=UTC))
        cls.article_masque = make_news(cls.source, 'Article masqué', status=False)

        cls.user = User.objects.create_user(
            email='lecteur@exemple.fr', password='mot-de-passe-solide', name='Lecteur',
            country=cls.france)

    def titres(self, response):
        return [article.title for article in response.context['news']]

    def test_liste_publique(self):
        response = self.client.get(reverse('news:list'))
        self.assertEqual(response.status_code, 200)

    def test_article_masque_absent_de_la_liste(self):
        response = self.client.get(reverse('news:list'))
        self.assertNotIn('Article masqué', self.titres(response))

    def test_visiteur_voit_lordre_chronologique(self):
        response = self.client.get(reverse('news:list'))
        self.assertEqual(self.titres(response)[0], 'Article mondial récent')

    def test_pays_suivi_en_tete_meme_plus_ancien(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('news:list'))
        titres = self.titres(response)
        self.assertEqual(titres[0], 'Article français ancien')
        # La priorité trie, elle ne filtre pas : le reste du monde reste visible.
        self.assertIn('Article mondial récent', titres)

    def test_recherche_dans_le_titre(self):
        response = self.client.get(reverse('news:list'), {'q': 'français'})
        self.assertEqual(self.titres(response), ['Article français ancien'])

    def test_fiche_inexistante_renvoie_404(self):
        url = reverse('news:detail', args=['00000000-0000-0000-0000-000000000000'])
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_lecture_compte_et_redirige_vers_lediteur(self):
        url = reverse('news:read', args=[self.article_monde.pk])
        response = self.client.get(url)

        self.assertRedirects(response, self.article_monde.url,
                             fetch_redirect_response=False)
        self.article_monde.refresh_from_db()
        self.assertEqual(self.article_monde.views, 1)

    def test_lecture_connectee_alimente_lhistorique_sans_doublon(self):
        self.client.force_login(self.user)
        url = reverse('news:read', args=[self.article_monde.pk])
        self.client.get(url)
        self.client.get(url)
        # Relire met à jour la date au lieu d'ajouter une ligne.
        self.assertEqual(UserNewsHistory.objects.filter(user=self.user).count(), 1)

    def test_lecture_visiteur_ne_cree_pas_dhistorique(self):
        self.client.get(reverse('news:read', args=[self.article_monde.pk]))
        self.assertFalse(UserNewsHistory.objects.exists())


class ToggleFavoriteTests(TestCase):
    """Tests de la vue toggle_favorite() qui ajoute ou retire un favori."""
    @classmethod
    def setUpTestData(cls):
        cls.article = make_news(make_source())
        cls.user = User.objects.create_user(
            email='lecteur@exemple.fr', password='mot-de-passe-solide', name='Lecteur')

    def setUp(self):
        self.url = reverse('news:toggle_favorite', args=[self.article.pk])

    def test_get_refuse(self):
        # Une action qui modifie des données ne doit jamais passer en GET :
        # un lien ou un préchargement suffirait à la déclencher.
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(self.url).status_code, 405)

    def test_visiteur_redirige_vers_la_connexion(self):
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('accounts:login'), response['Location'])
        self.assertFalse(UserNewsFavorite.objects.exists())

    def test_ajoute_puis_retire(self):
        self.client.force_login(self.user)

        self.client.post(self.url)
        self.article.refresh_from_db()
        self.assertTrue(UserNewsFavorite.objects.filter(user=self.user).exists())
        self.assertEqual(self.article.likes, 1)

        self.client.post(self.url)
        self.article.refresh_from_db()
        self.assertFalse(UserNewsFavorite.objects.filter(user=self.user).exists())
        self.assertEqual(self.article.likes, 0)

    def test_redirige_vers_la_fiche_et_nulle_part_ailleurs(self):
        self.client.force_login(self.user)
        response = self.client.post(self.url, {'next': 'https://site-malveillant.example'})
        self.assertRedirects(response, reverse('news:detail', args=[self.article.pk]))

    def test_pages_personnelles_reservees_aux_connectes(self):
        for name in ('news:favorites', 'news:history'):
            with self.subTest(page=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 302)

# La note n'est pas encore utilisé mais sera utilisé à l'avenir pour trier les articles par popularité. Il est important de vérifier que la note ne dépasse jamais 1, même si le nombre de favoris est supérieur au nombre de lectures.
class RatingTests(TestCase):
    """Tests de la méthode update_rating() qui calcule la note d'un article.
    Utile pour vérifier que la note ne dépasse jamais 1, même si le nombre de
    favoris est supérieur au nombre de lectures.
    """

    def test_note_nulle_sans_consultation(self):
        article = make_news(make_source())
        self.assertEqual(article.update_rating(), 0)

    def test_note_bornee_a_un(self):
        # Plus de favoris que de lectures arrive quand on ajoute un favori
        # depuis la liste sans ouvrir l'article : la note ne doit pas
        # dépasser la capacité de NUMERIC(3,2).
        article = make_news(make_source(), likes=5, views=2)
        self.assertEqual(article.update_rating(), 1)