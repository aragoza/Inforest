import uuid

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models


class UserManager(BaseUserManager):

    use_in_migrations = True

    def create_account(self, email, password, **extra):
        if not email:
            raise ValueError("adresse email obligatoire.")

        user = self.model(email=self.normalize_email(email), **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra):
        extra.setdefault('is_staff', False)
        extra.setdefault('is_superuser', False)
        return self.create_account(email, password, **extra)

    def create_superuser(self, email, password=None, **extra):
        extra.setdefault('is_staff', True)
        extra.setdefault('is_superuser', True)

        if not extra.get('is_staff') or not extra.get('is_superuser'):
            raise ValueError("Un administrateur doit avoir is_staff et is_superuser à True.")

        return self.create_account(email, password, **extra)


class User(AbstractUser):
    username = None
    first_name = None
    last_name = None
    date_joined = None

    id_user = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField('nom affiché', max_length=100)
    email = models.EmailField('adresse email', unique=True)
    country = models.ForeignKey('core.Country', on_delete=models.SET_NULL, null=True, blank=True, related_name='users', verbose_name='pays suivi')
    newsletter_option = models.BooleanField('inscrit au mail hebdomadaire', default=False)
    created_at = models.DateTimeField('date de création', auto_now_add=True)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['name']

    def __str__(self):
        return self.email