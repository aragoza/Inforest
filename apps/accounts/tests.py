"""Tests de l'application accounts.

Les comptes, le mail hebdomadaire et les droits RGPD (désinscription,
export, suppression). Les courriels ne partent nulle part : pendant les
tests, Django remplace le backend d'envoi par une boîte en mémoire,
mail.outbox, que l'on inspecte.
"""

import json
from datetime import timedelta
from io import StringIO

from django.core import mail
from django.core.management import call_command
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.core.models import Country, Source
from apps.news.models import News, UserNewsFavorite, UserNewsHistory
from apps.news.services import make_hash

from .forms import RegisterForm
from .models import User
from .newsletter import send_weekly, weekly_articles
from .tasks import send_weekly_task

PASSWORD = 'mot-de-passe-solide-42'


def make_user(email='abonne@exemple.fr', **extra):
    values = {'name': 'Abonné', 'newsletter_option': True}
    values.update(extra)
    return User.objects.create_user(email=email, password=PASSWORD, **values)


def make_news(source, title, days_ago=1, **extra):
    url = f'https://exemple.fr/{abs(hash(title))}'
    return News.objects.create(
        source=source, title=title, url=url, hash=make_hash(title, url),
        summary="Résumé de l'article.",
        published_at=timezone.now() - timedelta(days=days_ago), **extra)


# --------------------------------------------------------------------------
# Comptes
# --------------------------------------------------------------------------

class UserModelTests(TestCase):
    """Tests du modèle User, notamment la normalisation de l'adresse et la création d'un superutilisateur."""

    def test_creation_exige_une_adresse(self):
        with self.assertRaises(ValueError):
            User.objects.create_user(email='', password=PASSWORD, name='x')

    def test_domaine_normalise(self):
        user = make_user(email='Elliot@EXEMPLE.FR')
        self.assertEqual(user.email, 'Elliot@exemple.fr')

    def test_superutilisateur(self):
        admin = User.objects.create_superuser(email='admin@exemple.fr',
                                              password=PASSWORD, name='Admin')
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)

    def test_mail_hebdomadaire_desactive_par_defaut(self):
        # Consentement RGPD : l'inscription doit être un acte positif.
        user = User.objects.create_user(email='a@exemple.fr', password=PASSWORD, name='a')
        self.assertFalse(user.newsletter_option)

    def test_chaque_compte_a_son_propre_jeton(self):
        a, b = make_user('a@exemple.fr'), make_user('b@exemple.fr')
        self.assertNotEqual(a.newsletter_token, b.newsletter_token)


class RegistrationTests(TestCase):
    """Tests de l'inscription et de la connexion."""

    def form(self, **extra):
        data = {'name': 'Nouveau', 'email': 'nouveau@exemple.fr',
                'password1': PASSWORD, 'password2': PASSWORD}
        data.update(extra)
        return RegisterForm(data=data)

    def test_adresse_mise_en_minuscules(self):
        form = self.form(email='Nouveau@Exemple.FR')
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['email'], 'nouveau@exemple.fr')

    def test_doublon_refuse_quelle_que_soit_la_casse(self):
        make_user(email='nouveau@exemple.fr')
        form = self.form(email='NOUVEAU@exemple.fr')
        self.assertFalse(form.is_valid())
        self.assertIn('email', form.errors)

    def test_inscription_connecte_et_redirige(self):
        response = self.client.post(reverse('accounts:register'), {
            'name': 'Nouveau', 'email': 'nouveau@exemple.fr',
            'password1': PASSWORD, 'password2': PASSWORD})
        self.assertRedirects(response, reverse('home'))
        self.assertTrue(User.objects.filter(email='nouveau@exemple.fr').exists())
        self.assertIn('_auth_user_id', self.client.session)

    def test_connexion_par_adresse(self):
        make_user(email='lecteur@exemple.fr')
        response = self.client.post(reverse('accounts:login'), {
            'email': 'lecteur@exemple.fr', 'password': PASSWORD})
        self.assertRedirects(response, reverse('home'))

    def test_mauvais_mot_de_passe(self):
        make_user(email='lecteur@exemple.fr')
        response = self.client.post(reverse('accounts:login'), {
            'email': 'lecteur@exemple.fr', 'password': 'faux'})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_pages_du_compte_reservees_aux_connectes(self):
        for name in ('accounts:profile', 'accounts:preferences',
                     'accounts:export_data', 'accounts:delete_account'):
            with self.subTest(page=name):
                response = self.client.get(reverse(name))
                self.assertEqual(response.status_code, 302)
                self.assertIn(reverse('accounts:login'), response['Location'])


# --------------------------------------------------------------------------
# Sélection des articles du mail
# --------------------------------------------------------------------------

class WeeklyArticlesTests(TestCase):
    """"Tests de la fonction weekly_articles() qui sélectionne les articles à envoyer dans le mail hebdomadaire."""
    @classmethod
    def setUpTestData(cls):
        cls.source = Source.objects.create(name='S', feed_url='https://s.fr/feed')
        cls.france = Country.objects.create(iso_code='FR', name='France')

        cls.monde_recent = make_news(cls.source, 'Monde récent', days_ago=1)
        cls.france_ancien = make_news(cls.source, 'France ancienne', days_ago=5,
                                      country=cls.france)
        cls.trop_vieux = make_news(cls.source, 'Il y a un mois', days_ago=30)
        cls.masque = make_news(cls.source, 'Masqué', days_ago=1, status=False)

    def titres(self, user):
        return [article.title for article in weekly_articles(user)]

    def test_pays_suivi_dabord(self):
        user = make_user(country=self.france)
        self.assertEqual(self.titres(user), ['France ancienne', 'Monde récent'])

    def test_sans_pays_lactualite_mondiale(self):
        user = make_user()
        self.assertIn('Monde récent', self.titres(user))

    def test_exclut_les_articles_hors_semaine_et_masques(self):
        titres = self.titres(make_user())
        self.assertNotIn('Il y a un mois', titres)
        self.assertNotIn('Masqué', titres)

    def test_respecte_la_limite(self):
        for i in range(10):
            make_news(self.source, f'Article {i}')
        self.assertEqual(len(weekly_articles(make_user(), limit=5)), 5)

    def test_pas_de_doublon_entre_pays_et_complement(self):
        user = make_user(country=self.france)
        pks = [article.pk for article in weekly_articles(user)]
        self.assertEqual(len(pks), len(set(pks)))


# --------------------------------------------------------------------------
# Envoi du mail
# --------------------------------------------------------------------------

@override_settings(SITE_URL='https://inforet.example')
class SendWeeklyTests(TestCase):
    """Tests de la fonction send_weekly() qui envoie le mail hebdomadaire aux abonnés."""
    @classmethod
    def setUpTestData(cls):
        cls.source = Source.objects.create(name='Mongabay', feed_url='https://s.fr/feed')
        make_news(cls.source, "Les tourbières d'Indonésie se dégradent")

    def test_seuls_les_abonnes_actifs_recoivent(self):
        make_user('abonne@exemple.fr')
        make_user('non-abonne@exemple.fr', newsletter_option=False)
        make_user('inactif@exemple.fr', is_active=False)

        report = send_weekly()

        self.assertEqual(report['sent'], 1)
        self.assertEqual([m.to for m in mail.outbox], [['abonne@exemple.fr']])

    def test_garde_fou_contre_le_double_envoi(self):
        make_user()
        send_weekly()
        report = send_weekly()

        self.assertEqual(report['sent'], 0)
        self.assertEqual(len(mail.outbox), 1)

    def test_nouvel_envoi_possible_apres_le_delai(self):
        user = make_user()
        send_weekly()
        user.last_newsletter_sent_at = timezone.now() - timedelta(days=7)
        user.save()

        self.assertEqual(send_weekly()['sent'], 1)

    def test_essai_a_blanc_nenvoie_rien_et_ne_marque_rien(self):
        user = make_user()
        report = send_weekly(dry_run=True)

        user.refresh_from_db()
        self.assertEqual(report['sent'], 1)
        self.assertEqual(len(mail.outbox), 0)
        self.assertIsNone(user.last_newsletter_sent_at)

    def test_aucun_mail_vide(self):
        News.objects.all().delete()
        user = make_user()

        report = send_weekly()

        user.refresh_from_db()
        self.assertEqual(report['without_articles'], 1)
        self.assertEqual(len(mail.outbox), 0)
        # Pas marqué comme servi : il recevra le prochain mail utile.
        self.assertIsNone(user.last_newsletter_sent_at)

    def test_limite_par_lot(self):
        for i in range(3):
            make_user(f'abonne{i}@exemple.fr')

        report = send_weekly(max_per_run=2)

        self.assertEqual(report['sent'], 2)
        self.assertEqual(report['postponed'], 1)

    def test_les_moins_recemment_servis_passent_dabord(self):
        # Avec une limite par lot, personne ne doit être sacrifié à chaque
        # envoi : le moins récemment servi passe en premier.
        make_user('recent@exemple.fr',
                  last_newsletter_sent_at=timezone.now() - timedelta(days=8))
        make_user('ancien@exemple.fr',
                  last_newsletter_sent_at=timezone.now() - timedelta(days=30))

        send_weekly(max_per_run=1)

        self.assertEqual(mail.outbox[0].to, ['ancien@exemple.fr'])


@override_settings(SITE_URL='https://inforet.example')
class MessageContentTests(TestCase):
    """Tests du contenu du mail hebdomadaire, texte et HTML."""
    @classmethod
    def setUpTestData(cls):
        source = Source.objects.create(name='Mongabay', feed_url='https://s.fr/feed')
        cls.article = make_news(source, "Les tourbières d'Indonésie se dégradent")
        cls.user = make_user()

    def setUp(self):
        send_weekly()
        self.message = mail.outbox[0]
        self.html = self.message.alternatives[0][0]

    def test_versions_texte_et_html(self):
        self.assertTrue(self.message.body)
        self.assertEqual(self.message.alternatives[0][1], 'text/html')

    def test_texte_sans_echappement_html(self):
        # Sans {% autoescape off %}, l'apostrophe sortait en &#x27;.
        self.assertIn("d'Indonésie", self.message.body)
        self.assertNotIn('&#x27;', self.message.body)

    def test_entete_de_desinscription(self):
        url = (f'https://inforet.example/newsletter/desinscription/'
               f'{self.user.newsletter_token}/')
        self.assertEqual(self.message.extra_headers['List-Unsubscribe'], f'<{url}>')
        self.assertEqual(self.message.extra_headers['List-Unsubscribe-Post'],
                         'List-Unsubscribe=One-Click')

    def test_lien_de_desinscription_dans_le_corps(self):
        self.assertIn(str(self.user.newsletter_token), self.html)
        self.assertIn(str(self.user.newsletter_token), self.message.body)

    def test_liens_absolus(self):
        # Un mail n'a pas de requête HTTP : un lien relatif ne mènerait nulle part.
        self.assertIn(f'https://inforet.example/news/{self.article.pk}/', self.html)
        self.assertNotIn('href="/', self.html)

    def test_aucune_ressource_distante(self):
        # Une image ou une police distante signalerait l'ouverture à un tiers.
        self.assertNotIn('<img', self.html)
        self.assertNotIn('fonts.googleapis', self.html)


class SendWeeklyEntryPointsTests(TestCase):
    """Tests des points d'entrée de l'envoi du mail hebdomadaire : commande et tâche Celery."""
    def setUp(self):
        source = Source.objects.create(name='S', feed_url='https://s.fr/feed')
        make_news(source, 'Article')
        make_user()

    def test_commande_essai_a_blanc(self):
        out = StringIO()
        call_command('send_weekly', '--dry-run', stdout=out)
        self.assertIn('aucun mail envoyé', out.getvalue())
        self.assertIn('1 envoi', out.getvalue())
        self.assertEqual(len(mail.outbox), 0)

    def test_tache_renvoie_du_json(self):
        # Le retour d'une tâche traverse le broker : il doit être sérialisable.
        report = send_weekly_task()
        self.assertEqual(json.loads(json.dumps(report))['sent'], 1)


# --------------------------------------------------------------------------
# Droits RGPD
# --------------------------------------------------------------------------

class UnsubscribeTests(TestCase):
    """Tests de la vue newsletter_unsubscribe() qui désinscrit un abonné via le lien du mail."""
    def setUp(self):
        self.user = make_user()
        self.url = reverse('accounts:newsletter_unsubscribe',
                           args=[self.user.newsletter_token])

    def reload(self):
        self.user.refresh_from_db()
        return self.user.newsletter_option

    def test_get_affiche_sans_desinscrire(self):
        # Les messageries préchargent les liens : un GET ne doit rien changer.
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(self.reload())

    def test_post_desinscrit_sans_connexion(self):
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(self.reload())

    def test_post_de_la_messagerie_sans_jeton_csrf(self):
        # List-Unsubscribe-Post : c'est la messagerie qui poste, sans jeton
        # CSRF. La vue doit l'accepter.
        client = Client(enforce_csrf_checks=True)
        response = client.post(self.url, {'List-Unsubscribe': 'One-Click'})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(self.reload())

    def test_jeton_inconnu(self):
        url = reverse('accounts:newsletter_unsubscribe',
                      args=['00000000-0000-0000-0000-000000000000'])
        self.assertEqual(self.client.post(url).status_code, 404)
        self.assertTrue(self.reload())

    def test_ne_touche_quau_mail(self):
        self.client.post(self.url)
        self.assertTrue(User.objects.filter(pk=self.user.pk, is_active=True).exists())


class ExportDataTests(TestCase):
    """Tests de la vue export_data() qui fournit un fichier JSON des données personnelles."""
    def setUp(self):
        source = Source.objects.create(name='S', feed_url='https://s.fr/feed')
        self.article = make_news(source, 'Article favori')
        self.user = make_user()
        UserNewsFavorite.objects.create(user=self.user, news=self.article)
        UserNewsHistory.objects.create(user=self.user, news=self.article)
        self.client.force_login(self.user)

    def test_fichier_a_telecharger(self):
        response = self.client.get(reverse('accounts:export_data'))
        self.assertIn('attachment', response['Content-Disposition'])

    def test_contient_compte_favoris_et_historique(self):
        # Article 20 : l'export couvre aussi ce que l'utilisateur n'a pas
        # saisi lui-même, comme son historique de lecture.
        data = json.loads(self.client.get(reverse('accounts:export_data')).content)
        self.assertEqual(data['account']['email'], self.user.email)
        self.assertEqual(data['favorites'][0]['title'], 'Article favori')
        self.assertEqual(data['history'][0]['title'], 'Article favori')


class DeleteAccountTests(TestCase):
    """Tests de la vue delete_account() qui supprime un compte et ses traces."""

    def setUp(self):
        source = Source.objects.create(name='S', feed_url='https://s.fr/feed')
        article = make_news(source, 'Article')
        self.user = make_user()
        UserNewsFavorite.objects.create(user=self.user, news=article)
        UserNewsHistory.objects.create(user=self.user, news=article)
        self.client.force_login(self.user)
        self.url = reverse('accounts:delete_account')

    def test_mauvais_mot_de_passe_conserve_le_compte(self):
        self.client.post(self.url, {'password': 'faux', 'confirm': 'on'})
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())

    def test_confirmation_obligatoire(self):
        self.client.post(self.url, {'password': PASSWORD})
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())

    def test_suppression_efface_aussi_favoris_et_historique(self):
        # Article 17 : le CASCADE efface les traces liées au compte.
        response = self.client.post(self.url, {'password': PASSWORD, 'confirm': 'on'})

        self.assertRedirects(response, reverse('home'))
        self.assertFalse(User.objects.filter(pk=self.user.pk).exists())
        self.assertFalse(UserNewsFavorite.objects.exists())
        self.assertFalse(UserNewsHistory.objects.exists())
        self.assertEqual(News.objects.count(), 1)