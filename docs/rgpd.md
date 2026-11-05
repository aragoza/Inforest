# Données personnelles

Ce que le projet collecte, pourquoi, et comment chaque droit prévu par le
RGPD est exercé. Chaque droit renvoie au code qui le met en œuvre et au test
qui le vérifie.

## Données collectées

| Donnée | Où | Finalité | Base légale |
|---|---|---|---|
| Nom affiché, adresse email, mot de passe haché | `accounts_user` | Compte et connexion | Exécution du service (art. 6.1.b) |
| Pays suivi | `accounts_user.country` | Priorité régionale des actualités | Exécution du service |
| Inscription au mail hebdomadaire | `accounts_user.newsletter_option` | Envoi du mail | Consentement (art. 6.1.a) |
| Jeton de désinscription, date du dernier mail | `accounts_user` | Désinscription sans connexion, anti-double envoi | Consentement |
| Date de création, dernière connexion | `accounts_user` | Sécurité du compte | Exécution du service |
| Favoris | `news_usernewsfavorite` | Fonctionnalité demandée par l'utilisateur | Exécution du service |
| Historique de lecture | `news_usernewshistory` | Fonctionnalité demandée par l'utilisateur | Exécution du service |
| Session | `django_session` et cookie `sessionid` | Rester connecté | Strictement nécessaire |

Les visiteurs non connectés ne laissent aucune donnée personnelle dans la
base. Le compteur de consultations d'un article (`News.views`) est un total
anonyme.

**Minimisation.** Ni prénom, ni nom de famille, ni date de naissance, ni
adresse IP en base. Le nom affiché est libre.

## Cookies

| Cookie | Durée | Rôle |
|---|---|---|
| `sessionid` | 14 jours | maintenir la connexion |
| `csrftoken` | 1 an | protéger les formulaires contre la falsification de requête |

Les deux sont strictement nécessaires au fonctionnement : ils ne demandent pas
de consentement et ne justifient pas de bandeau. Aucun cookie de mesure
d'audience ni de publicité.

Le cookie de session est `HttpOnly`, donc inaccessible au JavaScript. Les
deux sont `SameSite=Lax`, et `Secure` dès que `DEBUG` est désactivé.

## Transferts vers des tiers

| Tiers | Données | Quand |
|---|---|---|
| Hébergeur | toutes, en tant que sous-traitant | en permanence |
| Resend | adresse et contenu du mail | à chaque envoi du mail hebdomadaire |
| Médias d'origine des articles | adresse IP du visiteur | quand il clique pour lire l'article |

Aucune ressource tierce n'est chargée à l'affichage d'une page : les polices
sont servies par le site, et le mail ne contient ni image ni police distante.
Le seul contact avec un tiers est un clic volontaire vers l'article d'origine.

## Exercice des droits

| Droit | Mise en œuvre | Code | Test |
|---|---|---|---|
| Information (art. 13) | Profil, section « Mes données » | `templates/accounts/profile.html` | — |
| Accès (art. 15) et portabilité (art. 20) | Export JSON du compte, des favoris et de l'historique | `accounts.views.export_data` | `ExportDataTests` |
| Rectification (art. 16) | Page de préférences | `accounts.views.preferences` | — |
| Effacement (art. 17) | Suppression du compte, avec mot de passe et confirmation ; favoris et historique effacés en cascade | `accounts.views.delete_account` | `DeleteAccountTests` |
| Retrait du consentement (art. 7.3) | Lien dans chaque mail, sans connexion ; en-tête `List-Unsubscribe` pour le bouton des messageries | `accounts.views.newsletter_unsubscribe` | `UnsubscribeTests` |

**Consentement au mail hebdomadaire.** La case est décochée par défaut, à
l'inscription comme dans le modèle (`newsletter_option` vaut `False`). Le
retrait est aussi simple que l'inscription : un clic depuis le mail, puis une
confirmation.

**Portabilité.** L'export inclut l'historique de lecture, que l'utilisateur
n'a pas saisi lui-même : l'article 20 couvre aussi les données générées par
son usage du service.

## Points ouverts

- **Durées de conservation.** Aucune purge automatique n'est en place. À
  définir : un compte inactif depuis trois ans, l'historique de lecture
  au-delà d'un an.
- **Export incomplet.** `last_newsletter_sent_at` et `is_active` ne figurent
  pas encore dans l'export ; l'article 15 porte sur toutes les données
  détenues.
- **Images distantes sur la fiche d'un article.** `templates/news/detail.html`
  affiche encore `image_url` quand le champ est rempli, ce qui transmet
  l'adresse IP du visiteur au serveur du média. La collecte ne remplit plus ce
  champ ; retirer le bloc du gabarit et le champ du modèle.
- **Contrat de sous-traitance** avec l'hébergeur et avec Resend, et région
  d'hébergement des données, à documenter au déploiement.