import uuid

from django.db import migrations


def generate_tokens(apps, schema_editor):
    """Donne un jeton distinct à chaque compte déjà en base."""
    User = apps.get_model('accounts', 'User')

    for user in User.objects.all():
        user.newsletter_token = uuid.uuid4()
        user.save(update_fields=['newsletter_token'])


class Migration(migrations.Migration):

    dependencies = [('accounts', '0003_newsletter_token')]

    operations = [
        # Pas d'opération inverse : revenir en arrière supprime la colonne.
        migrations.RunPython(generate_tokens, migrations.RunPython.noop),
    ]