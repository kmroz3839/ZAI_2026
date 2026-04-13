from django.db import IntegrityError
from django.shortcuts import render
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from rest_framework import permissions, viewsets, views
from rest_framework.decorators import api_view, action
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
import datetime, json
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from .serializers import ConversionRateSerializer, CustomCurrencySerializer
from .models import ConversionRate, CustomConversionRate, CustomCurrency
from .nbp_api import get_exchange_rate_for_date
from .custom_currency_api import get_nbp_or_custom_exchange_rate_for_date, fetch_user_custom_currencies, add_custom_currency, push_new_custom_exchange_rate, delete_custom_currency

# Create your views here.
class ConversionRateViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.AllowAny]
    queryset = ConversionRate.objects.all().order_by('-date_at')
    serializer_class = ConversionRateSerializer

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


class ConversionRateForDate(viewsets.ViewSet):
    permission_classes = [permissions.AllowAny]

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
        operation_description="Convert value to PLN using conversion rate for given code and date",
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

    @swagger_auto_schema(request_body=openapi.Schema(
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

class ManageCustomCurrency(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]
    
    @swagger_auto_schema(request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
            properties={
                'code': openapi.Schema(type=openapi.TYPE_STRING, description='currency code'),
            }
        ),
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
                return Response({"error": "already exists"}, status=400)
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