from django.db import models
from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    email = models.EmailField(unique=True)
    newsletter_option = models.BooleanField(default=False)
    # le pays et le reste viendront avec la base de données