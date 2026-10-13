import uuid
from django.db import models
from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    id_user = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=128)
    is_admin = models.BooleanField(default=False)
    newsletter_option = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    # le pays viendra avec la création de la table des pays