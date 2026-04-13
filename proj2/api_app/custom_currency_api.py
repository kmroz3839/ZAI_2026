from .models import CustomConversionRate, CustomCurrency
from .nbp_api import get_exchange_rate_for_date

def fetch_user_custom_currencies(uid):
    return CustomCurrency.objects.filter(user_id=uid)

def add_custom_currency(uid, code):
    newObj = CustomCurrency(user_id=uid, code=code)
    newObj.save()
    return newObj

def push_new_custom_exchange_rate(uid, code, rate, date_at):
    if len(CustomCurrency.objects.filter(user_id=uid, code=code)) > 0:
        try:
            obj = CustomConversionRate.objects.get(user_id=uid, from_currency=code, date_at=date_at)
            obj.delete()
        except CustomConversionRate.DoesNotExist:
            pass
        newObj = CustomConversionRate(user_id=uid, date_at=date_at, from_currency=code, to_currency='pln', rate=rate)
        newObj.save()
        return newObj
    else:
        return None

def get_custom_exchange_rate(uid, code, date_at):
    try:
        return CustomConversionRate.objects.get(user_id=uid, from_currency=code, date_at=date_at)
    except CustomConversionRate.DoesNotExist:
        return None
    
def get_nbp_or_custom_exchange_rate_for_date(uid, code, date_at):
    custom = get_custom_exchange_rate(uid, code, date_at)
    return custom if custom is not None else get_exchange_rate_for_date(code, date_at)

def delete_custom_currency(uid, code):
    try:
        curr = CustomCurrency.objects.get(user_id=uid, code=code)
        CustomConversionRate.objects.filter(user_id=uid, from_currency=code).delete()
        curr.delete()
        return True
    except CustomCurrency.DoesNotExist:
        return False