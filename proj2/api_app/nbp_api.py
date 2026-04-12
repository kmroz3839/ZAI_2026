import requests, json

from .models import ConversionRate

def fetch_exchange_rate_for_date(code, date_at):
    try:
        url = f"http://api.nbp.pl/api/exchangerates/rates/a/{code}/{date_at}/?format=json"
        response = requests.get(url)
        if response.status_code == 200:
            data = json.loads(response.text)
            return data["rates"][0]["mid"]
        else:
            return None
    except:
        return None
    
def get_exchange_rate_for_date(code, date_at):
    try:
        query = ConversionRate.objects.get(from_currency=code, to_currency="pln", date_at=date_at)
        return query
    except ConversionRate.DoesNotExist:
        rate = fetch_exchange_rate_for_date(code, date_at)
        if rate is not None:
            new_entry = ConversionRate(date_at=date_at, from_currency=code, to_currency="pln", rate=rate)
            new_entry.save()
            return new_entry
        else:
            return None
