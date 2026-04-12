from django.contrib import admin
from import_export import resources

from .models import ConversionRate, CustomConversionRate, CustomCurrency

# Register your models here.

admin.site.register(ConversionRate)
admin.site.register(CustomCurrency)
admin.site.register(CustomConversionRate)

class ConversionsResource(resources.ModelResource):
    class Meta:
        model = ConversionRate
        
class CustomConversionsResource(resources.ModelResource):
    class Meta:
        model = CustomConversionRate

class CustomCurrencyResource(resources.ModelResource):
    class Meta:
        model = CustomCurrency