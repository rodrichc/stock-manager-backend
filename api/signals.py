from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
from .models import Cuenta 

@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def crear_cuenta_usuario(sender, instance, created, **kwargs):
    """
    Se ejecuta automáticamente después de que un Usuario es guardado.
    Si el usuario es nuevo (created=True), le crea su billetera.
    """
    if created:
        Cuenta.objects.create(usuario=instance, saldo_ars=0, saldo_usd=0)
        print(f"✅ Billetera creada automáticamente para: {instance.username}")