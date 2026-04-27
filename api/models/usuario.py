from django.db import models
from django.contrib.auth.models import AbstractUser

class Usuario(AbstractUser):
    email = models.EmailField(unique=True)

    class Meta:
        app_label = "api"

    def __str__(self):
        return self.username