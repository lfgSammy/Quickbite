import re
from django.contrib.auth import authenticate
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from drf_spectacular.utils import extend_schema
from .models import User, Notification
from .serializers import UserSerializer, NotificationSerializer, LoginSerializer, RegisterSerializer

def validate_email(email):
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email)

def validate_password(password):
    errors = []
    if len(password) < 8:
        errors.append('Password cannot be less than 8 characters')
    if not re.search(r'[A-Z]', password):
        errors.append('Password must contain at least an uppercase letter')
    if not re.search(r'[a-z]', password):
        errors.append('Password must contain at least a lowercase letter')
    if not re.search(r'[0-9]', password):
        errors.append('Password must contain at least a number')
    return errors

class RegisterView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(request=RegisterSerializer)
    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')
        email = request.data.get('email')
        phone_number = request.data.get('phone_number', '')

        if not username or not email or not password:
            return Response({'error':'All fields are required'}, status=status.HTTP_400_BAD_REQUEST)
        
        if not validate_email(email):
            return Response({'error':'Invalid email format'}, status=status.HTTP_400_BAD_REQUEST)
        
        # --- FIX 1: Invoke the validation function ---
        password_errors = validate_password(password)
        if password_errors:
            return Response({'error': password_errors}, status=status.HTTP_400_BAD_REQUEST)
      
        if User.objects.filter(username=username).exists():
            return Response({'error':'Username already exist'}, status=status.HTTP_400_BAD_REQUEST)
            
        if User.objects.filter(email=email).exists():
            return Response({'error':'Email already exist'}, status=status.HTTP_400_BAD_REQUEST)
        
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            phone_number=phone_number if phone_number else None,
            role='customer'
        )

        refresh = RefreshToken.for_user(user)    
        return Response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': UserSerializer(user).data
        }, status=status.HTTP_201_CREATED)

class AssignRoleView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, user_id):
        # only admin can assign roles
        if not request.user.is_admin:
            return Response({'error': 'Only admins can assign roles'},
                            status=status.HTTP_403_FORBIDDEN)

        new_role = request.data.get('role')
        valid_roles = ['customer', 'kitchen', 'admin']

        if new_role not in valid_roles:
            return Response(
                {'error': f'Invalid role. Choose from {valid_roles}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        user = User.objects.filter(id=user_id).first()
        if not user:
            return Response({'error': 'User not found'},
                            status=status.HTTP_404_NOT_FOUND)

        user.role = new_role
        user.save()

        return Response({
            'message': f'{user.username} role updated to {new_role}',
            'user': UserSerializer(user).data
        })

class LoginView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(request=LoginSerializer)
    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')
        user = authenticate(username=username, password=password)
        if not user:
            return Response({'error':'Invalid Credentials'}, status=status.HTTP_401_UNAUTHORIZED)
        refresh = RefreshToken.for_user(user)
        return Response({
            'access': str(refresh.access_token),
            'refresh': str(refresh), # kept your original key typo 'refresh'
            'user': UserSerializer(user).data
        }, status=status.HTTP_200_OK)
        

class ProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # --- FIX 2: Pass request.user instance ---
        serializer = UserSerializer(request.user)
        return Response(serializer.data)
    
    def patch(self, request):
        serializer = UserSerializer(request.user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
class NotificationListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # --- FIX 3: Close filter parentheses correctly ---
        notification = Notification.objects.filter(user=request.user).order_by('-created_at')
        serializer = NotificationSerializer(notification, many=True)
        return Response(serializer.data)
    
    def patch(self, request):
        Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
        return Response({'message':'All notifications are read'})