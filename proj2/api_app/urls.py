from django.urls import path

from .views import ConversionRateForDate, ConversionRateViewSet, ConvertFromPLN, ConvertFromPLNAuth, ConvertFromPLNUnauth, ConvertToPLN, AuthGetToken, AuthRegisterUser, ConvertToPLNAuth, ConvertToPLNUnauth, ListCustomCurrencies
from .views import ManageCustomCurrency, ListCustomCurrencyExchangeRates, AdminManageConversionRates

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
    path("user/customcurrency/convrates/", ListCustomCurrencyExchangeRates.as_view({'get': 'list'}), name='custom_currency_get_rates'),

    path("managedb/convrates/export/", AdminManageConversionRates.as_view({'get': 'bulk_export'}), name='admin_bulk_export_conv_rates'),
    path("managedb/convrates/import/", AdminManageConversionRates.as_view({'post': 'bulk_import'}), name='admin_bulk_import_conv_rates'),

    path("auth/get-token/", AuthGetToken.as_view(), name="api_token_auth"),
    path("auth/register/", AuthRegisterUser.as_view(), name="api_register_user"),
]