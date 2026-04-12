from django.db import models

# Create your models here.

class ConversionRate(models.Model):
    date_at = models.DateField()
    from_currency = models.CharField(max_length=3)
    to_currency = models.CharField(max_length=3)
    rate = models.FloatField()

    def __str__(self):
        return f"[{self.date_at}] {self.from_currency} -> {self.to_currency}: {self.rate}" 
    
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['from_currency', 'to_currency', 'date_at'], 
                name='uniq_conv_rate_for_date'
            )
        ]


class CustomCurrency(models.Model):
    code = models.CharField(max_length=3)
    user_id = models.IntegerField(null=False, blank=False)

    def __str__(self):
        return f"(user {self.user_id}) {self.code}"
    
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['code', 'user_id'],
                name='uniq_custom_currency_for_user'
            )
        ]


class CustomConversionRate(ConversionRate):
    user_id = models.IntegerField(null=False, blank=False)

    def __str__(self):
        return f"(custom: user {self.user_id}) {ConversionRate.__str__(self)}" 