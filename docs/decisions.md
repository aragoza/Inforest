# Décisions techniques

Chaque décision est présentée avec ce qui l'a motivée et ce qu'elle coûte. Les
alternatives écartées sont nommées : un choix ne se comprend qu'à côté de ce
qu'on a refusé.

---

## Données et modèle

### Une application `core` pour les référentiels partagés

**Décision.** `Country` et `Source` vivent dans `core`, pas dans `accounts` ni
dans `news`.

**Pourquoi.** Deux applications ont besoin des pays. Placée dans l'une, la
table rend l'autre dépendante sans raison. `Source` servira aussi à
`discovery`, d'où les indicateurs `for_news` et `for_discovery`.

### Déduplication par empreinte

**Décision.** Un article est identifié par le SHA-1 de son titre normalisé et
de son URL canonique, stocké dans `News.hash` avec une contrainte d'unicité.

**Pourquoi.** Une même page circule sous plusieurs URL : paramètres de suivi,
majuscules dans le domaine, barre oblique finale. L'URL brute laisserait
passer des doublons. La contrainte en base, et non une vérification dans le
code, empêche aussi deux collectes simultanées d'enregistrer le même article.

**Alternative écartée.** Comparer les URL brutes, ou vérifier l'existence
avant d'insérer : fragile face aux variations, et ouvert aux accès concurrents.

### Clés primaires composées pour les favoris et l'historique

**Décision.** `(user, news)` est la clé primaire des deux tables de liaison,
comme dans le MCD.

**Pourquoi.** Un favori en double devient impossible au niveau de la base.
Django 5.2 le permet nativement.

**Coût.** Ces modèles ne peuvent pas être enregistrés dans l'administration.
C'est acceptable, et même sain au regard du RGPD : l'historique de lecture
d'un utilisateur n'a pas à être consultable par un administrateur.

### `SET_NULL` plutôt que `CASCADE` sur les pays

**Décision.** Supprimer un pays du référentiel met à `NULL` le pays des
comptes et des articles.

**Pourquoi.** Retirer une ligne d'un référentiel ne doit pas supprimer des
comptes. `NULL` a un sens : actualité mondiale, ou utilisateur sans pays suivi.

### La base décrite par `DATABASE_URL`

**Décision.** Une seule variable d'environnement porte le moteur, l'hôte et
les identifiants, avec SQLite par défaut.

**Pourquoi.** Le projet se lance sans rien installer sur un poste sans Docker,
et les conteneurs comme la production utilisent PostgreSQL sans qu'une ligne
de code change.

**Coût.** Deux bases coexistent sur un poste de développement, avec des
données différentes. Voir `exploitation.md`.

---

## Collecte

### Normaliser plutôt que choisir un format

**Décision.** `feedparser` lit RSS 2.0 et Atom 1.0, et `normalize_entry`
produit un dictionnaire aux clés stables quel que soit le format d'origine.

**Pourquoi.** Imposer un format aux médias n'est pas possible. Le reste du
code ne voit qu'une seule forme de données.

### Valider un flux avant d'en enregistrer le contenu

**Décision.** Un flux sans norme reconnue, vide, ou dont moins de 90 % des
entrées ont un titre et un lien est refusé et compte comme un échec.

**Pourquoi.** Une source qui change de format ou renvoie une page HTML ne doit
pas remplir la base d'articles sans titre.

### Désactivation automatique après cinq échecs

**Décision.** Une source qui échoue cinq fois de suite passe à
`status=False`. Réactiver depuis l'administration remet le compteur à zéro.

**Pourquoi.** Un flux mort allonge chaque collecte d'un délai d'attente. Le
seuil laisse passer une panne passagère.

### Reconnaissance du pays : le terme le plus long d'abord, en mot entier

**Décision.** Les termes sont triés du plus long au plus court et cherchés
entre des frontières de mot.

**Pourquoi.** Sans tri, « Guinée » serait trouvé dans « Guinée équatoriale ».
Sans frontières de mot, « France » serait trouvé dans « Francesca ». Les
termes saisis dans l'administration acceptent trois lettres, pour « RDC ».

### Ne stocker que le titre, le résumé et le lien

**Décision.** Le texte intégral et les images restent chez l'éditeur.

**Pourquoi.** Citer un titre et un résumé court en renvoyant à la source est
défendable. Reproduire l'article ou son image, qui est une œuvre distincte et
souvent sous licence d'agence, ne l'est pas.

---

## Tâches planifiées

### Celery, Celery Beat et Redis

**Décision.** La collecte et le mail hebdomadaire sont des tâches Celery
planifiées par Beat, avec Redis comme broker.

**Pourquoi.** L'architecture permet ensuite de confier un traitement long à
un processus de fond depuis une requête web.

**Alternative écartée.** Le planificateur de l'hébergeur appelant les
commandes de gestion. Plus simple pour deux tâches déclenchées par l'horloge,
et sans broker ; écarté au profit d'une architecture extensible.

### Sérialisation JSON, jamais pickle

**Décision.** `CELERY_TASK_SERIALIZER = 'json'` et
`CELERY_ACCEPT_CONTENT = ['json']`.

**Pourquoi.** Désérialiser du pickle exécute le code qu'il contient. Une
écriture non autorisée dans la file deviendrait une exécution de code sur le
worker.

### Des tâches sans argument

**Décision.** Les tâches ne reçoivent aucun argument et renvoient des types
simples.

**Pourquoi.** Les arguments transitent par Redis et apparaissent dans les
journaux du worker. Une adresse passée en argument serait une donnée
personnelle recopiée hors de la base, hors du `CASCADE` de suppression.

### Le fuseau de Celery indépendant de celui de Django

**Décision.** `CELERY_TIMEZONE = 'Europe/Paris'`.

**Pourquoi.** Les heures du `crontab` sont lues dans le fuseau de Celery. En
UTC, le mail du lundi 8 h partirait à 9 h en hiver et 10 h en été.

### `config/__init__.py` importe l'application Celery

**Décision.** Le paquet `config` importe `config.celery` au démarrage.

**Pourquoi.** `@shared_task` cherche « l'application courante » à la première
utilisation. Sans cet import, un `.delay()` appelé depuis Django part vers une
application par défaut sans broker, et la tâche se perd sans erreur. Le worker
et Beat, eux, continuent de fonctionner : la panne ne se voit que côté Django.

---

## Mail hebdomadaire

### Jeton de désinscription stocké en base

**Décision.** `User.newsletter_token`, UUID unique, plutôt qu'un jeton signé
avec `SECRET_KEY`.

**Pourquoi.** Les liens déjà envoyés survivent à une rotation de la clé
secrète. Un lien de désinscription mort est un défaut de conformité.

**Coût.** Trois migrations pour ajouter le champ : un défaut appelable sur un
champ unique n'est évalué qu'une fois par l'`ALTER TABLE`, donc une migration
intermédiaire attribue un jeton distinct à chaque compte existant avant la
pose de la contrainte.

### Désinscription en deux temps, sans connexion

**Décision.** Un `GET` affiche une confirmation, un `POST` désinscrit. Aucune
connexion n'est demandée.

**Pourquoi.** Les messageries préchargent les liens : un `GET` qui
désinscrirait serait déclenché par un simple aperçu. Exiger une connexion
pour se désinscrire est un obstacle que la loi interdit.

### `csrf_exempt` sur la vue de désinscription

**Décision.** La seule vue du projet exemptée de la protection CSRF.

**Pourquoi.** L'en-tête `List-Unsubscribe-Post` fait poster la messagerie
elle-même, sans jeton CSRF. La protection CSRF empêche un site tiers d'agir
avec la session d'une victime ; ici l'action ne dépend d'aucune session, mais
du seul jeton présent dans l'URL. Qui le connaît peut déjà faire la requête.

### Garde-fou contre le double envoi

**Décision.** Un abonné servi depuis moins de six jours est ignoré, et la
date est enregistrée après chaque envoi.

**Pourquoi.** Deux Beat lancés par erreur, ou un redéploiement pendant
l'envoi, ne doivent pas doubler les messages.

### Gabarit de messagerie

**Décision.** Tableaux, styles en attributs, police système, aucune image ni
ressource distante, liens absolus construits sur `SITE_URL`.

**Pourquoi.** Les messageries ignorent les feuilles de style externes et
Outlook interprète mal les mises en page modernes. Une ressource distante
signale l'ouverture du message à un tiers. Un mail n'a pas de requête HTTP
pour en déduire son propre domaine.

---

## Sécurité et confidentialité

### Polices servies par le site

**Décision.** Fraunces et Inter, en polices variables réduites au jeu latin,
dans `static/fonts/`, au lieu de Google Fonts.

**Pourquoi.** Un lien vers Google Fonts transmet l'adresse IP de chaque
visiteur à Google avant tout consentement. Un tribunal allemand a condamné
un site pour ce motif en 2022. Les deux polices pèsent 157 Ko.

### Chiffrement SMTP actif par défaut

**Décision.** `EMAIL_USE_TLS = env.bool('EMAIL_USE_TLS', default=True)`.

**Pourquoi.** MailDev n'implémente pas STARTTLS et le désactive dans son
environnement. Mais une variable oubliée en production doit laisser le
chiffrement actif plutôt que de faire partir identifiants et adresses en clair.

### Image Docker sans secret ni donnée

**Décision.** Utilisateur non privilégié, et `.dockerignore` qui exclut
`.env`, `db.sqlite3` et les mails de prévisualisation.

**Pourquoi.** Une image se partage. Les secrets arrivent à l'exécution.

### Dépendances entièrement épinglées

**Décision.** `requirements.txt` fixe aussi les dépendances indirectes, et
épingle `packaging` explicitement.

**Pourquoi.** `kombu` 5.7.0 importe `packaging` dans son transport Redis sans
le déclarer : toute installation partant de zéro échouait au premier
`.delay()`. Épingler l'ensemble garantit qu'une image reconstruite dans six
mois contient les mêmes versions.