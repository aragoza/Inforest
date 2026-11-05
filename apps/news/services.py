"""Collecte des flux RSS et écriture en base.

Le découpage suit le trajet d'un article :
    téléchargement  ->  fetch_feed()
    validation      ->  validate_feed()
    normalisation   ->  normalize_entry()    (dictionnaire aux clés stables)
    pertinence      ->  is_about_forests()
    pays            ->  detect_country()
    déduplication   ->  make_hash()
    enregistrement  ->  save_entries()       (table News)

Les étapes avant l'enregistrement ne touchent pas à la base : elles restent
testables sans réseau.
"""

import hashlib
import logging
import re
import unicodedata
from datetime import UTC, datetime
from urllib.parse import parse_qsl, urlencode, urlparse

import feedparser
import requests
from django.db import transaction

from apps.core.models import Country, Source

from .feeds import FOREST_KEYWORDS
from .models import News

logger = logging.getLogger(__name__)

USER_AGENT = 'Mozilla/5.0 (compatible; InForestBot/0.1; charlet.elliot@gmail.com)'

FEED_HEADERS = {
    'User-Agent': USER_AGENT,
    'Accept': 'application/rss+xml, application/atom+xml, application/xml;q=0.9, */*;q=0.8',
    'Accept-Language': 'fr,en;q=0.8',
}
TIMEOUT = 10
MAX_PER_FEED = 50
MAX_SUMMARY = 500


MIN_TITLE_RATIO = 0.9
MIN_LINK_RATIO = 0.9

TRACKING_PARAMS = (
    'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content',
    'utm_id', 'fbclid', 'gclid', 'mc_cid', 'mc_eid',
)


# --------------------------------------------------------------------------
# Outils de texte
# --------------------------------------------------------------------------

def normalize_text(text):
    """Minuscules et accents retirés"""
    if not text:
        return ''

    decomposed = unicodedata.normalize('NFKD', text)

    without_accents = ''
    for character in decomposed:
        if not unicodedata.combining(character):
            without_accents += character

    return without_accents.lower()


def strip_html(text):
    """Retire les balises HTML et les espaces en trop d'un résumé"""
    if not text:
        return ''

    without_tags = re.sub(r'<[^>]+>', ' ', text)
    single_spaces = re.sub(r'\s+', ' ', without_tags)
    return single_spaces.strip()


def shorten(text, limit=MAX_SUMMARY):
    """Tronque un texte à la limite"""
    if len(text) <= limit:
        return text

    cut = text[:limit]
    last_space = cut.rfind(' ')

    if last_space > 0:
        cut = cut[:last_space]

    return cut + '…'


# --------------------------------------------------------------------------
# Outils d'URL
# --------------------------------------------------------------------------

def normalize_url(url):
    """Forme canonique d'une URL : schéma et domaine en minuscules, paramètres de suivi retirés, slash final retiré"""
    if not url:
        return ''

    parts = urlparse(url.strip())

    scheme = parts.scheme.lower()
    domain = parts.netloc.lower()
    path = parts.path.rstrip('/')

    kept_params = []
    for name, value in parse_qsl(parts.query):
        if name.lower() not in TRACKING_PARAMS:
            kept_params.append((name, value))

    clean_url = f'{scheme}://{domain}{path}'

    if kept_params:
        clean_url = clean_url + '?' + urlencode(kept_params)

    return clean_url


def make_hash(title, url):
    """Empreinte d'un article : titre normalisé + URL canonique.

    C'est la clé de déduplication enregistrée en base. SHA-1 suffit : il ne
    s'agit pas de sécurité mais d'identifier deux contenus identiques.
    """
    fingerprint = normalize_text(title) + '|' + normalize_url(url)
    return hashlib.sha1(fingerprint.encode('utf-8')).hexdigest()


# --------------------------------------------------------------------------
# Lecture d'un flux
# --------------------------------------------------------------------------

def fetch_feed(url):
    """Télécharge un flux et renvoie l'objet analysé par feedparser"""
    response = requests.get(url, timeout=TIMEOUT, headers=FEED_HEADERS)
    response.raise_for_status()
    return feedparser.parse(response.content)


def validate_feed(feed):
    """Vérifie qu'un flux analysé est exploitable. Renvoie un dictionnaire"""
    if not feed.version:
        return {
            'is_valid': False,
            'problems': ["ce n'est pas un flux (aucune norme RSS ou Atom reconnue)"],
        }

    entries = feed.entries

    if len(entries) == 0:
        return {'is_valid': False, 'problems': ['le flux ne contient aucune entrée']}

    with_title = 0
    with_link = 0

    for entry in entries:
        if entry_title(entry):
            with_title += 1
        if entry_link(entry):
            with_link += 1

    problems = []

    if with_title / len(entries) < MIN_TITLE_RATIO:
        missing = len(entries) - with_title
        problems.append(f'{missing} entrée(s) sur {len(entries)} sans titre')

    if with_link / len(entries) < MIN_LINK_RATIO:
        missing = len(entries) - with_link
        problems.append(f'{missing} entrée(s) sur {len(entries)} sans lien')

    return {'is_valid': len(problems) == 0, 'problems': problems}


def describe_feed(feed):
    """Statistiques descriptives d'un flux, pour le diagnostic"""
    entries = feed.entries

    with_date = 0
    with_summary = 0
    with_image = 0

    for entry in entries:
        if entry_published(entry):
            with_date += 1
        if entry_summary(entry):
            with_summary += 1
        if entry_image(entry):
            with_image += 1

    return {
        'title': feed.feed.get('title', '(sans titre)'),
        'version': feed.version or '(inconnue)',
        'entries': len(entries),
        'with_date': with_date,
        'with_summary': with_summary,
        'with_image': with_image,
    }


# --------------------------------------------------------------------------
# Lecture d'une entrée
# --------------------------------------------------------------------------


def entry_title(entry):
    return strip_html(entry.get('title', ''))


def entry_link(entry):
    return entry.get('link', '').strip()


def entry_summary(entry):
    return strip_html(entry.get('summary', ''))


def entry_published(entry):
    """Date de publication en UTC, ou None si le flux n'en fournit pas"""
    parsed_date = entry.get('published_parsed')

    if not parsed_date:
        parsed_date = entry.get('updated_parsed')

    if not parsed_date:
        return None

    return datetime(
        year=parsed_date[0],
        month=parsed_date[1],
        day=parsed_date[2],
        hour=parsed_date[3],
        minute=parsed_date[4],
        second=parsed_date[5],
        tzinfo=UTC,
    )


def entry_image(entry):
    """Première image trouvée, quel que soit l'endroit où le flux la range"""
    # Atom
    for key in ('media_content', 'media_thumbnail'):
        medias = entry.get(key) or []
        for media in medias:
            if media.get('url'):
                return media['url']

    # RSS
    links = entry.get('links') or []
    for link in links:
        is_enclosure = link.get('rel') == 'enclosure'
        is_image = str(link.get('type', '')).startswith('image/')
        if is_enclosure and is_image:
            return link.get('href', '')

    return ''


def normalize_entry(entry, source):
    """Transforme une entrée feedparser en dictionnaire aux clés stables"""
    title = entry_title(entry)
    url = normalize_url(entry_link(entry))

    return {
        'title': title[:300],
        'url': url[:1000],
        'summary': shorten(entry_summary(entry)),
        'image_url': entry_image(entry)[:1000],
        'published_at': entry_published(entry),
        'language': source.language,
        'hash': make_hash(title, url),
    }


def is_about_forests(article):
    """Vrai si le titre ou le résumé contient l'un des mots-clés forestiers"""
    text = normalize_text(article['title'] + ' ' + article['summary'])

    for keyword in FOREST_KEYWORDS:
        if keyword in text:
            return True

    return False


# --------------------------------------------------------------------------
# Reconnaissance du pays
# --------------------------------------------------------------------------

def build_country_terms():
    """Liste de couples (terme, identifiant de pays), du plus long au plus court."""
    country_terms = []

    for country in Country.objects.all():
        for term, min_length in country.match_terms():
            normalized = normalize_text(term)
            if len(normalized) >= min_length:
                country_terms.append((normalized, country.id_country))

    country_terms.sort(key=term_length, reverse=True)
    return country_terms


def term_length(country_term):
    """Longueur du terme, pour trier les couples (terme, identifiant)"""
    return len(country_term[0])


def detect_country(article, country_terms):
    """Identifiant du pays cité dans l'article, ou None"""
    text = normalize_text(article['title'] + ' ' + article['summary'])

    for term, country_id in country_terms:
        pattern = r'\b' + re.escape(term) + r'\b'
        if re.search(pattern, text):
            return country_id

    return None


# --------------------------------------------------------------------------
# Enregistrement
# --------------------------------------------------------------------------

def save_entries(source, entries, only_forests=True, country_terms=None):
    """Enregistre les entrées d'un flux"""
    if country_terms is None:
        country_terms = build_country_terms()

    created_count = 0
    skipped_count = 0

    for entry in entries[:MAX_PER_FEED]:
        article = normalize_entry(entry, source)

        if not article['url'] or not article['title']:
            skipped_count += 1
            continue

        if only_forests and not is_about_forests(article):
            skipped_count += 1
            continue

        article['source'] = source
        article['country_id'] = detect_country(article, country_terms)

        saved_article, is_new = News.objects.get_or_create(
            hash=article['hash'],
            defaults=article,
        )

        if is_new:
            created_count += 1
        else:
            skipped_count += 1

    return {'created': created_count, 'skipped': skipped_count}


def fetch_source(source, only_forests=True, country_terms=None):
    """Collecte une source et met à jour son état de santé"""
    if country_terms is None:
        country_terms = build_country_terms()

    nothing_collected = {'created': 0, 'skipped': 0}

    try:
        feed = fetch_feed(source.feed_url)
    except requests.RequestException as error:
        logger.warning('Source %s injoignable : %s', source.name, error)
        source.mark_failure(error)
        return nothing_collected

    validation = validate_feed(feed)

    if not validation['is_valid']:
        reason = ' ; '.join(validation['problems'])
        logger.warning('Source %s inexploitable : %s', source.name, reason)
        source.mark_failure('Flux inexploitable : ' + reason)
        return nothing_collected

    with transaction.atomic():
        counts = save_entries(source, feed.entries, only_forests, country_terms)

    source.mark_success()
    return counts


def fetch_all(only_forests=True):
    """Collecte toutes les sources actives. Renvoie un rapport par source"""
    country_terms = build_country_terms()

    sources = Source.objects.filter(status=True, for_news=True)

    report = []

    for source in sources:
        counts = fetch_source(source, only_forests, country_terms)
        report.append({
            'source': source,
            'created': counts['created'],
            'skipped': counts['skipped'],
            'has_failed': source.consecutive_failures > 0,
        })

    return report