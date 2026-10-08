from django.db import models


Class News(models.Model):
    id_news = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=300)
    text = models.TextField()
    link = models.CharField(max_length=200)
    published_at = models.DateTimeField(auto_now_add=True)
    theme = models.CharField(max_length=20)
    views = models.IntegerField(default=0)
    likes = models.IntegerField(default=0)
    rating = models.FloatField(default=0.0) # ajouter une fonction d'auto-update du rating en fonction des likes et des vues
    status = models.CharField(max_length=20)
    # source et pays viendront avec la création de ses tables et ses relations
