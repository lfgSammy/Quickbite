import hmac
import hashlib
import requests
from django.conf import settings
from django.utils import timezone
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from .models import Payment
from .serializers import PaymentSerializer
from order.models import Order
from users.models import Notification

class initializePaymentView(APIView):
    permission_classes = [IsAuthenticated]

