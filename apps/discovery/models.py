from django.db import models


Class Discovery(models.Model):
    id_discovery = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=300)
    text = models.TextField()
    link = models.CharField(max_length=200)
    theme = models.CharField(max_length=20)
    views = models.IntegerField(default=0)
    likes = models.IntegerField(default=0)
    rating = models.FloatField(default=0.0) # ajouter une fonction d'auto-update du rating en fonction des likes et des vues
    status = models.CharField(max_length=20)
    # pays viendra avec la création de sa table et sa relation 
