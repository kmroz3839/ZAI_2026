from rest_framework import serializers
from .models import ConversionRate, CustomCurrency

class ConversionRateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConversionRate
        fields = ['date_at', 'from_currency', 'to_currency', 'rate']

class CustomCurrencySerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomCurrency
        fields = ['code']