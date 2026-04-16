import datetime, json
from django.db import IntegrityError
from django.http import FileResponse
from django.shortcuts import render
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from rest_framework import permissions, viewsets, views
from rest_framework.decorators import api_view, action
from rest_framework.parsers import JSONParser
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from import_export import resources
from sendfile import sendfile
from tablib import Dataset

from .serializers import ConversionRateSerializer, CustomCurrencySerializer
from .models import ConversionRate, CustomConversionRate, CustomCurrency
from .nbp_api import get_exchange_rate_for_date
from .admin import ConversionsResource
from .custom_currency_api import get_nbp_or_custom_exchange_rate_for_date, fetch_user_custom_currencies, add_custom_currency, push_new_custom_exchange_rate, delete_custom_currency

# Create your views here.
class ConversionRateViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.AllowAny]
    queryset = ConversionRate.objects.all().order_by('-date_at')
    serializer_class = ConversionRateSerializer

    @swagger_auto_schema(
        operation_description="List conversion rates. Optional query parameters: code (filter by currency code), date_at (filter by date in format YYYY-MM-DD)",
        manual_parameters=[
            openapi.Parameter('code', openapi.IN_QUERY, description="currency code to filter by", type=openapi.TYPE_STRING),
            openapi.Parameter('date_at', openapi.IN_QUERY, description="date to filter by in format YYYY-MM-DD", type=openapi.TYPE_STRING)
        ]
    )
    def list(self, request):
        #return super().list(self, request)
        qs = self.get_queryset()
        searchparams = self.request.query_params
        if "code" in searchparams:
            qs = qs.filter(from_currency=searchparams["code"])
        if "date_at" in searchparams:
            qs = qs.filter(date_at=searchparams["date_at"])
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        else:
            serializer = self.get_serializer(qs, many=True)
            return Response(serializer.data, status=200)

class AdminManageConversionRates(viewsets.ViewSet):
    permission_classes = [permissions.IsAdminUser]

    @swagger_auto_schema(operation_description="Bulk export all conversion rates in database to CSV")
    def bulk_export(self, request):
        dataset = ConversionsResource().export()
        data = dataset.export("csv")
        return FileResponse(data, content_type='text/csv', filename='conversion_rates.csv')
        #response = Response(data, content_type='text/csv')
        #response['Content-Disposition'] = 'attachment; filename="conversion_rates.csv"'
        #return response

    @swagger_auto_schema(
        operation_description="Bulk import conversion rates from a CSV file",
        manual_parameters=[openapi.Parameter('file', openapi.IN_FORM, description="CSV file to import", type=openapi.TYPE_FILE)]
    )
    def bulk_import(self, request):
        if 'file' not in request.FILES:
            return Response({"error": "file is required"}, status=400)
        file = request.FILES['file']
        dataset = Dataset().load(file.read().decode('utf-8'), format='csv')
        result = ConversionsResource().import_data(dataset, format='csv')
        if result.has_errors():
            return Response({"error": "invalid CSV format"}, status=400)
        else:
            return Response({"message": "import successful"}, status=200)

class ConversionRateForDate(viewsets.ViewSet):
    permission_classes = [permissions.AllowAny]

    @swagger_auto_schema(operation_description="Get conversion rate for a given currency code and date. Optional query parameter: date_at (date in format YYYY-MM-DD, default: today)")
    def retrieve(self, request: Request, code=None, date_at=None):
        #kwargs = self.request.parser_context.get('kwargs')
        #code = kwargs["code"]
        #date_at = kwargs["date_at"]
        if date_at is None:
            date_at = datetime.date.today()
        obj = get_exchange_rate_for_date(code, date_at)
        if obj is None:
            return Response({"error": "conversion rate not found for given code and date"}, status=404)
        serializer = ConversionRateSerializer(obj)
        return Response(serializer.data)

class ConvertToPLN(viewsets.ViewSet):
    parser_classes = [JSONParser]

    def do(self, request: Request):
        try:
            requestbody = json.loads(self.request.body)
            code = requestbody["code"] if "code" in requestbody else None
            date_at = requestbody["date_at"] if "date_at" in requestbody else None
            value = requestbody["value"] if "value" in requestbody else None
            if code is None or value is None:
                return Response({"error": "code and value are required"}, status=400)
            
            if date_at is None:
                date_at = datetime.date.today()
            
            obj = get_nbp_or_custom_exchange_rate_for_date(request.user.pk, code, date_at) if request.user is not None else get_exchange_rate_for_date(code, date_at)
            if obj is None:
                return Response({"error": "conversion rate not found for given code and date"}, status=404)
            converted_value = value * obj.rate
            return Response({"converted_value": converted_value})
        except json.JSONDecodeError:
            return Response({"error": "invalid JSON"}, status=400)

class ConvertToPLNUnauth(ConvertToPLN):
    permission_classes = [permissions.AllowAny]
    @swagger_auto_schema(request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT, 
            properties={
                'code': openapi.Schema(type=openapi.TYPE_STRING, description='currency code'),
                'value': openapi.Schema(type=openapi.TYPE_NUMBER, description='value to convert'),
                'date_at': openapi.Schema(type=openapi.TYPE_STRING, description='date for conversion rate in format YYYY-MM-DD (optional, default: today)'),
            }
        ),
        operation_description="Convert value to PLN",
        responses={
            200: openapi.Response('Success', openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'converted_value': openapi.Schema(type=openapi.TYPE_NUMBER, description='number'),
                })),
            400: openapi.Response('Bad Request', openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'error': openapi.Schema(type=openapi.TYPE_STRING, description='error message'),
                }))
        }
    )
    def retrieve(self, request):
        requestbody = json.loads(self.request.body)
        code = requestbody["code"] if "code" in requestbody else None
        if code in ["usd", "eur", "gbp"]:
            return self.do(request)
        else:
            return Response({"error": "not authenticated. currency codes available for non-authenticated users: usd, eur, gbp"}, status=400)
        
class ConvertToPLNAuth(ConvertToPLN):
    permission_classes = [permissions.IsAuthenticated]
    @swagger_auto_schema(request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT, 
            properties={
                'code': openapi.Schema(type=openapi.TYPE_STRING, description='currency code'),
                'value': openapi.Schema(type=openapi.TYPE_NUMBER, description='value to convert'),
                'date_at': openapi.Schema(type=openapi.TYPE_STRING, description='date for conversion rate in format YYYY-MM-DD (optional, default: today)'),
            }
        ),
        operation_description="Convert value to PLN",
        responses={
            200: openapi.Response('Success', openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'converted_value': openapi.Schema(type=openapi.TYPE_NUMBER, description='number'),
                })),
            400: openapi.Response('Bad Request', openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'error': openapi.Schema(type=openapi.TYPE_STRING, description='error message'),
                }))
        }
    )
    def retrieve(self, request):
        return self.do(request)

class ConvertFromPLN(viewsets.ViewSet):
    parser_classes = [JSONParser]

    def do(self, request):
        try:
            requestbody = json.loads(self.request.body)
            code = requestbody["code"] if "code" in requestbody else None
            date_at = requestbody["date_at"] if "date_at" in requestbody else None
            value = requestbody["value"] if "value" in requestbody else None
            if code is None or value is None:
                return Response({"error": "code and value are required"}, status=400)
            
            if date_at is None:
                date_at = datetime.date.today()
            
            obj = get_nbp_or_custom_exchange_rate_for_date(request.user.pk, code, date_at) if request.user is not None else get_exchange_rate_for_date(code, date_at)
            if obj is None:
                return Response({"error": "conversion rate not found for given code and date"}, status=404)
            converted_value = value / obj.rate
            return Response({"converted_value": converted_value})
        except json.JSONDecodeError:
            return Response({"error": "invalid JSON"}, status=400)    
        
class ConvertFromPLNUnauth(ConvertFromPLN):
    permission_classes = [permissions.AllowAny]

    @swagger_auto_schema(request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT, 
            properties={
                'code': openapi.Schema(type=openapi.TYPE_STRING, description='currency code'),
                'value': openapi.Schema(type=openapi.TYPE_NUMBER, description='value to convert'),
                'date_at': openapi.Schema(type=openapi.TYPE_STRING, description='date for conversion rate in format YYYY-MM-DD (optional, default: today)'),
            }
        ),
        operation_description="Convert value from PLN",
        responses={
            200: openapi.Response('Success', openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'converted_value': openapi.Schema(type=openapi.TYPE_NUMBER, description='number'),
                })),
            400: openapi.Response('Bad Request', openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'error': openapi.Schema(type=openapi.TYPE_STRING, description='error message'),
                }))
        }
    )
    def retrieve(self, request, *args, **kwargs):
        requestbody = json.loads(self.request.body)
        code = requestbody["code"] if "code" in requestbody else None
        if code in ["usd", "eur", "gbp"]:
            return self.do(request)
        else:
            return Response({"error": "not authenticated. currency codes available for non-authenticated users: usd, eur, gbp"}, status=400)

class ConvertFromPLNAuth(ConvertFromPLN):
    permission_classes = [permissions.IsAuthenticated]

    @swagger_auto_schema(request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT, 
            properties={
                'code': openapi.Schema(type=openapi.TYPE_STRING, description='currency code'),
                'value': openapi.Schema(type=openapi.TYPE_NUMBER, description='value to convert'),
                'date_at': openapi.Schema(type=openapi.TYPE_STRING, description='date for conversion rate in format YYYY-MM-DD (optional, default: today)'),
            }
        ),
        operation_description="Convert value from PLN",
        responses={
            200: openapi.Response('Success', openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'converted_value': openapi.Schema(type=openapi.TYPE_NUMBER, description='number'),
                })),
            400: openapi.Response('Bad Request', openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'error': openapi.Schema(type=openapi.TYPE_STRING, description='error message'),
                }))
        }
    )
    def retrieve(self, request):
        return self.do(request)

class AuthGetToken(views.APIView):
    permission_classes = [permissions.AllowAny]
    parser_classes = [JSONParser]

    @swagger_auto_schema(request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
            properties={
                'username': openapi.Schema(type=openapi.TYPE_STRING, description='username'),
                'password': openapi.Schema(type=openapi.TYPE_STRING, description='password'),
            }
        ),
        operation_description="Obtain authentication token by providing username and password",
        responses={
            200: openapi.Response('Success', openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'token': openapi.Schema(type=openapi.TYPE_STRING, description='authentication token'),
                })),
            400: openapi.Response('Bad Request', openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'error': openapi.Schema(type=openapi.TYPE_STRING, description='error message'),
                })),
            401: openapi.Response('Unauthorized', openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'error': openapi.Schema(type=openapi.TYPE_STRING, description='error message'),
                }))
        }
    )
    def post(self, request):
        try:
            json_data = json.loads(request.body)
            username = json_data["username"] if "username" in json_data else None
            password = json_data["password"] if "password" in json_data else None
            if username is None or password is None:
                return Response({"error": "username and password are required"}, status=400)
            user = authenticate(username=username, password=password)
            if user is not None:
                token, created = Token.objects.get_or_create(user=user)
                return Response({"token": token.key})
            else:
                return Response({"error": "invalid credentials"}, status=401)
        except json.JSONDecodeError:
            return Response({"error": "invalid JSON"}, status=400)
        
class AuthRegisterUser(views.APIView):
    permission_classes = [permissions.AllowAny]
    parser_classes = [JSONParser]

    @swagger_auto_schema(request_body=openapi.Schema(
        operation_description="Create a new user account and obtain auth token",
        type=openapi.TYPE_OBJECT,
            properties={
                'username': openapi.Schema(type=openapi.TYPE_STRING, description='desired username'),
                'password': openapi.Schema(type=openapi.TYPE_STRING, description='desired password'),
            }
        ),
        responses={
            200: openapi.Response('Success', openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'token': openapi.Schema(type=openapi.TYPE_STRING, description='authentication token'),
                })),
            400: openapi.Response('Bad Request', openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'error': openapi.Schema(type=openapi.TYPE_STRING, description='error message'),
                }))
        }
    )
    def post(self, request):
        try:
            json_data = json.loads(request.body)
            username = json_data["username"] if "username" in json_data else None
            password = json_data["password"] if "password" in json_data else None
            if username is None or password is None:
                return Response({"error": "username and password are required"}, status=400)
            if User.objects.filter(username=username).exists():
                return Response({"error": "username already exists"}, status=400)
            user = User.objects.create_user(username=username, password=password)
            user.save()
            token = Token.objects.create(user=user)
            return Response({"token": token.key})
        except json.JSONDecodeError:
            return Response({"error": "invalid JSON"}, status=400)


class ListCustomCurrencies(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = CustomCurrencySerializer

    def get_queryset(self):
        uid = self.request.user.pk
        return fetch_user_custom_currencies(uid)
    
    @swagger_auto_schema(operation_description="List custom currencies added by the authenticated user")
    def list(self, request):
        return super().list(request)

class ManageCustomCurrency(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [JSONParser]
    
    @swagger_auto_schema(request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
            properties={
                'code': openapi.Schema(type=openapi.TYPE_STRING, description='currency code'),
            }
        ),
        operation_description="Define a new custom currency",
        responses={
            201: openapi.Response('Created', openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'token': openapi.Schema(type=openapi.TYPE_STRING, description='authentication token'),
                })),
            400: openapi.Response('Bad Request', openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'error': openapi.Schema(type=openapi.TYPE_STRING, description='error message'),
                }))
        }
    )
    def create(self, request):
        try:
            json_data = json.loads(request.body)
            code = json_data["code"]
            uid = request.user.pk
            try:
                newObj = add_custom_currency(uid, code)
                return Response(CustomCurrencySerializer(newObj).data, status=201)
            except IntegrityError:
                return Response({"error": "validation failed or already exists"}, status=400)
        except json.JSONDecodeError:
            return Response({"error": "invalid JSON"}, status=400)   
    
    
    @swagger_auto_schema(request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'code': openapi.Schema(type=openapi.TYPE_STRING, description='currency code'),
        }
    ),
        responses={
            200: openapi.Response('Success', openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'message': openapi.Schema(type=openapi.TYPE_STRING, description='success message'),
                })),
            400: openapi.Response('Bad Request', openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'error': openapi.Schema(type=openapi.TYPE_STRING, description='error message'),
                }))
        }
    )
    def remove(self, request):
        try:
            json_data = json.loads(request.body)
            code = json_data["code"]
            if delete_custom_currency(request.user.pk, code):
                return Response(None, status=200)
            else:
                return Response({"error": "not found"}, status=404)
        except json.JSONDecodeError:
            return Response({"error": "invalid JSON"}, status=400)
         
    @swagger_auto_schema(request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'code': openapi.Schema(type=openapi.TYPE_STRING, description='currency code'),
                'rate': openapi.Schema(type=openapi.TYPE_NUMBER, description='exchange rate'),
                'date_at': openapi.Schema(type=openapi.TYPE_STRING, description='date of the exchange rate'),
            }
        ),
        operation_description="Push a new custom exchange rate for the authenticated user",
        responses={
            200: openapi.Response('Success', openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'message': openapi.Schema(type=openapi.TYPE_STRING, description='success message'),
                })),
            400: openapi.Response('Bad Request', openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'error': openapi.Schema(type=openapi.TYPE_STRING, description='error message'),
                }))
        }
    )
    def push_rate(self, request):
        try:
            json_data = json.loads(request.body)
            code = json_data["code"]
            rate = json_data["rate"]
            date_at = json_data["date_at"] if "date_at" in json_data else datetime.date.today()
            uid = request.user.pk
            newObj = push_new_custom_exchange_rate(uid, code, rate, date_at)
            if newObj is None:
                return Response({"error": "custom currency with given code does not exist"}, status=404)
            else:
                return Response(ConversionRateSerializer(newObj).data, status=200)
        except json.JSONDecodeError:
            return Response({"error": "invalid JSON"}, status=400)
        

class ListCustomCurrencyExchangeRates(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ConversionRateSerializer

    def get_queryset(self):
        uid = self.request.user.pk
        return CustomConversionRate.objects.filter(user_id=uid).order_by('-date_at')

    @swagger_auto_schema(operation_description="List custom exchange rates for the authenticated user. Optional query parameters: code, date_at")
    def list(self, request):
        #return super().list(self, request)
        qs = self.get_queryset()
        searchparams = self.request.query_params
        if "code" in searchparams:
            qs = qs.filter(from_currency=searchparams["code"])
        if "date_at" in searchparams:
            qs = qs.filter(date_at=searchparams["date_at"])
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        else:
            serializer = self.get_serializer(qs, many=True)
            return Response(serializer.data, status=200)
        
class UserActions(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]

    @swagger_auto_schema(operation_description="Delete the current user account and all their data")
    def delete(self, request):
        uid = request.user.pk
        CustomCurrency.objects.filter(user_id=uid).delete()
        CustomConversionRate.objects.filter(user_id=uid).delete()
        request.user.delete()
        return Response({"message": "user deleted"}, status=200)