FROM python:3.14-slim

# Pas de fichiers .pyc, et sortie non tamponnée pour que les journaux du
# conteneur arrivent en direct plutôt que par blocs.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Les dépendances avant le code. Docker met chaque instruction en cache :
# tant que requirements.txt ne change pas, cette couche est réutilisée et un
# changement de code ne réinstalle rien.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Utilisateur non privilégié. Un processus root dans un conteneur qui
# s'échappe est root sur la machine hôte.
RUN useradd --create-home --uid 1000 inforest \
 && chown -R inforest:inforest /app
USER inforest

EXPOSE 8000

# 0.0.0.0 et non 127.0.0.1 : dans un conteneur, se lier à la boucle locale
# rend le service injoignable depuis l'hôte.
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]