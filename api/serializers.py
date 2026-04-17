from rest_framework import serializers
from .models import Activo, Operacion
from django.contrib.auth import get_user_model

User = get_user_model()


class OperacionSerializer(serializers.ModelSerializer):
    dolar_ccl = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, allow_null=True)
    activo = serializers.SlugRelatedField(
        queryset=Activo.objects.all(),
        slug_field='ticker'
    )

    class Meta:
        model = Operacion
        fields = ['id', 'tipo_operacion', 'activo', 'fecha', 'nominales', 'moneda', 'precio_unitario', 'dolar_ccl']
        read_only_fields = ['id']


class ListarOperacionSerializer(serializers.ModelSerializer):
    ticker = serializers.CharField(source='activo.ticker', read_only=True)
    ratio = serializers.IntegerField(source='activo.ratio', read_only=True)
    costo_accion_entera_usd = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = Operacion
        # NUEVO: Agregamos tipo_operacion
        fields = ['id', 'tipo_operacion', 'activo', 'ticker', 'ratio', 'fecha', 'nominales', 'moneda', 'precio_unitario', 'dolar_ccl', 'costo_accion_entera_usd']
        read_only_fields = ['id']

class RegistroSerializer(serializers.ModelSerializer):
    # Ponemos write_only=True para que la contraseña nunca se devuelva en un GET por seguridad
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['username', 'email', 'password'] # Podés sumar 'first_name' o 'last_name' si querés

    def create(self, validated_data):
        # create_user es fundamental porque encripta la contraseña automáticamente
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data.get('email', ''),
            password=validated_data['password']
        )
        return user