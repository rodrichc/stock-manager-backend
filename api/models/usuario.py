from django.contrib.auth.models import AbstractUser

class Usuario(AbstractUser):
    class Meta:
        app_label = "api"

    def __str__(self):
        return self.username