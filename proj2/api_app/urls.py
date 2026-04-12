from django.urls import path

from .views import ConversionRateForDate, ConversionRateViewSet, ConvertFromPLN, ConvertFromPLNAuth, ConvertFromPLNUnauth, ConvertToPLN, AuthGetToken, AuthRegisterUser, ConvertToPLNAuth, ConvertToPLNUnauth, ListCustomCurrencies
from .views import ManageCustomCurrency

urlpatterns = [
    path("public/convrates/", ConversionRateViewSet.as_view({'get': 'list'}), name='all_conv_rates'),
    path("public/convrates/<slug:code>/<slug:date_at>/", ConversionRateForDate.as_view({'get': 'retrieve'}), name='conv_rates_for_date'),
    path("public/topln", ConvertToPLNUnauth.as_view({'post': 'retrieve'}), name='currency_to_pln'),
    path("public/frompln", ConvertFromPLNUnauth.as_view({'post': 'retrieve'}), name='currency_from_pln'),

    path("user/topln", ConvertToPLNAuth.as_view({'post': 'retrieve'}), name='currency_to_pln'),
    path("user/frompln", ConvertFromPLNAuth.as_view({'post': 'retrieve'}), name='currency_from_pln'),
    path("user/customcurrency", ListCustomCurrencies.as_view({'get': 'list'}), name='custom_currency_list_for_id'),
    path("user/customcurrency/", ManageCustomCurrency.as_view({'post': 'create', 'delete': 'remove'}), name='custom_currency_delete'),
    path("user/customcurrency/rate/", ManageCustomCurrency.as_view({'post': 'push_rate'}), name='custom_currency_push_rate'),

    path("auth/get-token/", AuthGetToken.as_view(), name="api_token_auth"),
    path("auth/register/", AuthRegisterUser.as_view(), name="api_register_user"),
]