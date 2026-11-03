from celery import shared_task
from celery.utils.log import get_task_logger

from .newsletter import send_weekly

logger = get_task_logger(__name__)


@shared_task(name='accounts.send_weekly')
def send_weekly_task():
    """Aucun argument : pas de donnée personnelle à faire transiter par le broker."""
    report = send_weekly()

    logger.info('%s abonné(s), %s envoi(s), %s sans article, %s reporté(s)',
                report['subscribers'], report['sent'],
                report['without_articles'], report['postponed'])

    return report