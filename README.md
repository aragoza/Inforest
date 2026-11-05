# InForêt

Une application web pour suivre l'état des forêts du monde, pensée pour un
public francophone non spécialiste. Elle rassemble en un seul endroit des
actualités issues de médias spécialisés, des contenus de découverte, une
carte des forêts et un mail hebdomadaire centré sur le pays de l'utilisateur.

Projet de fin de formation, titre professionnel *Développeur web et web
mobile*.

## Fonctionnalités

- **Actualités** — collectées trois fois par jour depuis des flux RSS,
  dédupliquées et filtrées sur le thème forestier. Un utilisateur connecté
  voit d'abord celles qui concernent le pays qu'il suit.
- **Favoris et historique** — pour retrouver un article mis de côté ou déjà lu.
- **Mail hebdomadaire** — sur inscription explicite, chaque lundi, avec
  désinscription en un clic depuis le message.
- **Données personnelles** — export de toutes ses données et suppression du
  compte depuis le profil.
- **Supervision des sources** — un flux qui échoue cinq fois de suite se
  désactive seul ; l'administration affiche l'état de chacun.
- **Découverte** et **carte des forêts** — en cours de développement.

## Technique

Python 3.14 · Django 5.2 · PostgreSQL 17 · Celery 5.6 et Redis 7 · Docker
Compose · gabarits Django et CSS, sans framework JavaScript.

## Démarrer avec Docker

Prérequis : Docker et Docker Compose.

```bash
git clone https://github.com/aragoza/Inforest.git
cd Inforest
cp .env.example .env
```

Renseigner `SECRET_KEY` dans `.env`. Pour en générer une :

```bash
python -c "from django.core.management.utils import get_random_secret_key as g; print(g())"
```

**Elle ne doit contenir aucun `$`** : Docker Compose l'interpréterait comme
une variable et transmettrait une clé tronquée. Relancer la commande si c'est
le cas.

Puis :

```bash
docker compose up --build
```

Dans un second terminal, peupler la base au premier lancement :

```bash
docker compose exec web python manage.py createsuperuser
docker compose exec web python manage.py seed_countries
docker compose exec web python manage.py seed_sources --active
docker compose exec web python manage.py fetch_feeds
```

| Adresse | |
|---|---|
| http://localhost:8000 | le site |
| http://localhost:8000/admin | l'administration |
| http://localhost:1080 | MailDev, le visuel des mails envoyés par l'application |

## Démarrer sans Docker

Prérequis : Python 3.14.

```bash
python -m venv .venv
source .venv/bin/activate          # Windows : .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # puis renseigner SECRET_KEY

python manage.py migrate
python manage.py createsuperuser
python manage.py seed_countries
python manage.py seed_sources --active
python manage.py fetch_feeds
python manage.py runserver
```

Sans `DATABASE_URL`, le projet utilise SQLite et ne demande rien d'autre.
Les tâches planifiées demandent Redis ; sans lui, la collecte et le mail
restent disponibles par leurs commandes, `fetch_feeds` et `send_weekly`.

## Configuration

Toutes les variables sont listées et commentées dans `.env.example`. Les
principales :

| Variable | Rôle | Défaut |
|---|---|---|
| `SECRET_KEY` | clé de signature de Django | — obligatoire |
| `DEBUG` | mode développement | `False` |
| `DATABASE_URL` | base de données | SQLite local |
| `CELERY_BROKER_URL` | file des tâches | `redis://localhost:6379/0` |
| `EMAIL_BACKEND`, `EMAIL_HOST`… | envoi des courriels | écriture dans `sent_emails/` |
| `SITE_URL` | domaine utilisé dans les liens des mails | `http://127.0.0.1:8000` |

## Commandes

| Commande | Effet |
|---|---|
| `seed_countries` | insère les 249 pays, noms en français |
| `seed_sources [--active]` | insère les flux de `apps/core/feeds.py` |
| `fetch_feeds [--all] [--source <uuid>]` | collecte les sources actives |
| `send_weekly [--dry-run]` | envoie le mail hebdomadaire |

Dans Docker, les préfixer par `docker compose exec web python manage.py`.
Détails et diagnostic des pannes dans [`docs/exploitation.md`](docs/exploitation.md).

## Tests

```bash
python manage.py test apps
# ou dans Docker :
docker compose exec web python manage.py test apps
```

110 tests, sans accès au réseau : les flux RSS sont des exemples intégrés et
les téléchargements sont simulés. Ils couvrent :

- le pipeline de collecte — normalisation des URL, empreinte de
  déduplication, validation RSS et Atom, filtre forestier, reconnaissance du
  pays, désactivation d'une source défaillante ;
- les vues d'actualités — priorité du pays suivi, compteur de lecture,
  historique, favoris réservés aux connectés et en `POST` uniquement ;
- le mail hebdomadaire — sélection des destinataires, garde-fou contre le
  double envoi, essai à blanc, en-têtes de désinscription, liens absolus ;
- les droits RGPD — désinscription sans connexion, export, suppression en
  cascade ;
- l'administration — absence de requête supplémentaire par ligne affichée.

Le résultat attendu est `OK (expected failures=2)`. Ces deux échecs attendus
documentent une limite connue du filtre forestier, qui compare par simple
inclusion de chaîne : « boissons » y passe pour contenir « bois ». Le jour où
le filtre sera corrigé, ils deviendront des « réussites inattendues » et le
décorateur `@expectedFailure` devra être retiré.

## Structure

```
apps/
  core/        pays, sources de flux, commandes seed_*
  accounts/    comptes, droits RGPD, mail hebdomadaire
  news/        actualités, favoris, historique, collecte des flux
  discovery/   contenus de découverte
  maps/        carte des forêts
config/        réglages, URL racines, application Celery
templates/     gabarits HTML, dont les courriels dans emails/
static/        CSS et polices
docs/          documentation
```

## Documentation

- [`docs/architecture.md`](docs/architecture.md) — applications, flux de
  collecte et d'envoi, modèle de données
- [`docs/decisions.md`](docs/decisions.md) — les choix techniques et ce
  qu'ils coûtent
- [`docs/exploitation.md`](docs/exploitation.md) — commandes, tâches
  planifiées, pannes connues
- [`docs/rgpd.md`](docs/rgpd.md) — données collectées, cookies, exercice des
  droits

## Auteur

Elliot Charlet