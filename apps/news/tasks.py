from celery import shared_task
from celery.utils.log import get_task_logger

from .services import fetch_all

logger = get_task_logger(__name__)


@shared_task(name='news.fetch_feeds')
def fetch_feeds_task():
    """Collecte toutes les sources actives.

    La valeur de retour traverse le broker : elle ne contient que des types
    convertibles en JSON, jamais un objet Source.
    """
    report = fetch_all()

    created = sum(line['created'] for line in report)
    failed = [line['source'].name for line in report if line['has_failed']]

    logger.info('%s source(s), %s article(s) créé(s), %s en échec',
                len(report), created, len(failed))

    return {'sources': len(report), 'created': created, 'failed': failed}