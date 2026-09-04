import re
from django.contrib.auth import authenticate
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from drf_spectacular.utils import extend_schema
from Quickbite.pagination import PaginatedListMixin
from Quickbite.permissions import IsAdmin, IsAdminOrReadOnly
from .models import User, Notification, OperatingHours
from .serializers import UserSerializer, NotificationSerializer, LoginSerializer, RegisterSerializer
from django.utils import timezone
from social_django.utils import psa
from rest_framework_simplejwt.tokens import RefreshToken
import requests as http_requests
from django.conf import settings
from django.core.mail import send_mail
from .models import PasswordResetOTP


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

class GoogleOAuthView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = 'login'

    def post(self, request):
        code = request.data.get('code')
        redirect_url = request.data.get('redirect_url')

        if not code:
            return Response({'error':'Authorization code is required'},
                        status=status.HTTP_400_BAD_REQUEST)
        
        token_url = 'https://oauth2.googleapis.com/token'
        token_data = {
            'code':code,
            'client_id': settings.SOCIAL_AUTH_GOOGLE_OAUTH2_KEY,
            'client_secret': settings.SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET,
            'redirect_url':redirect_url,
            'grant_type':'authorization_code',
        }
        token_response = http_requests.post(token_url, data=token_data)
        token_json = token_response.json()

        if 'error' in token_json:
            return Response({'error':'Failed to exchange code for token'},
                            status=status.HTTP_400_BAD_REQUEST)
        access_token = token_json.get('access_token')

        # get user info from Google
        user_info_url = 'https://www.googleapis.com/oauth2/v2/userinfo'
        user_info_response = http_requests.get(
            user_info_url,
            headers={'Authorization': f'Bearer {access_token}'}
        )
        user_info = user_info_response.json()

        email = user_info.get('email')
        name = user_info.get('name', '')
        google_id = user_info.get('id')

        if not email:
            return Response({'error': 'Could not get email from Google'},
                            status=status.HTTP_400_BAD_REQUEST)

        # normalize so this matches an existing account regardless of casing
        email = email.lower()

        # get or create user
        user = User.objects.filter(email__iexact=email).first()

        if not user:
            # create new user from Google account
            username = email.split('@')[0]
            # ensure username is unique
            base_username = username
            counter = 1
            while User.objects.filter(username=username).exists():
                username = f"{base_username}{counter}"
                counter += 1

            user = User.objects.create_user(
                username=username,
                email=email,
                password=None,  # no password for OAuth users
                role='customer'
            )
            # set unusable password
            user.set_unusable_password()
            user.save()

        # generate JWT tokens
        refresh = RefreshToken.for_user(user)
        return Response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': UserSerializer(user).data
        })


class RegisterView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = 'register'

    @extend_schema(request=RegisterSerializer)
    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')
        email = request.data.get('email')
        phone_number = request.data.get('phone_number', '')

        if not username or not email or not password:
            return Response({'error':'All fields are required'}, status=status.HTTP_400_BAD_REQUEST)

        # normalize so "User@x.com" and "user@x.com" are treated as the same email
        email = email.lower()

        if not validate_email(email):
            return Response({'error':'Invalid email format'}, status=status.HTTP_400_BAD_REQUEST)

        # --- FIX 1: Invoke the validation function ---
        password_errors = validate_password(password)
        if password_errors:
            return Response({'error': password_errors}, status=status.HTTP_400_BAD_REQUEST)

        if User.objects.filter(username=username).exists():
            return Response({'error':'Username already exist'}, status=status.HTTP_400_BAD_REQUEST)

        if User.objects.filter(email__iexact=email).exists():
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

class ForgotPasswordView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = 'password_reset'

    # Identical for every request, so the response can't be used to test
    # whether an address has an account here.
    GENERIC_RESPONSE = {'message': 'OTP has been sent to your email'}

    def post(self, request):
        email = request.data.get('email')
        if not email:
            return Response({'error': 'Email is required'},
                            status=status.HTTP_400_BAD_REQUEST)

        user = User.objects.filter(email__iexact=email.lower()).first()
        if not user:
            return Response(self.GENERIC_RESPONSE)

        PasswordResetOTP.objects.filter(
            user=user, is_used=False).update(is_used=True)

        code = PasswordResetOTP.generate_codes()
        PasswordResetOTP.objects.create(user=user, code=code)

        send_mail(
            subject='QuickBite - Password reset OTP',
            message=f'''Hi {user.username},

You requested a password reset for your QuickBite account.

Your OTP is: {code}

This code expires in 10 minutes.

If you did not request this, please ignore this email.

QuickBite Team
''',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=True,
        )

        return Response(self.GENERIC_RESPONSE)


class VerifyResetOTPView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = 'otp_verify'

    def post(self, request):
        email = request.data.get('email')
        code = request.data.get('code')

        if not email or not code:
            return Response({'error': 'Email and OTP are required'},
                            status=status.HTTP_400_BAD_REQUEST)

        user = User.objects.filter(email__iexact=email.lower()).first()
        if not user:
            return Response({'error': 'Invalid OTP'},
                            status=status.HTTP_400_BAD_REQUEST)

        otp = PasswordResetOTP.objects.filter(
            user=user,
            code=code,
            is_used=False
        ).order_by('-created_at').first()

        if not otp:
            return Response({'error': 'Invalid OTP'},
                            status=status.HTTP_400_BAD_REQUEST)

        if not otp.is_valid():
            return Response({'error': 'OTP has expired. Request a new one.'},
                            status=status.HTTP_400_BAD_REQUEST)

        # mark OTP as used
        otp.is_used = True
        otp.save()

        # generate a temporary reset token
        import secrets
        reset_token = secrets.token_urlsafe(32)

        # store reset token temporarily
        from django.core.cache import cache
        cache.set(f'password_reset_{reset_token}', user.id, timeout=600)

        return Response({
            'message': 'OTP verified successfully',
            'reset_token': reset_token
        })


class ResetPasswordView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = 'otp_verify'

    def post(self, request):
        reset_token = request.data.get('reset_token')
        new_password = request.data.get('new_password')
        confirm_password = request.data.get('confirm_password')

        if not reset_token or not new_password:
            return Response({'error': 'Reset token and new password are required'},
                            status=status.HTTP_400_BAD_REQUEST)

        if new_password != confirm_password:
            return Response({'error': 'Passwords do not match'},
                            status=status.HTTP_400_BAD_REQUEST)

        # validate password strength
        password_errors = validate_password(new_password)
        if password_errors:
            return Response({'error': password_errors},
                            status=status.HTTP_400_BAD_REQUEST)

        # get user from reset token
        from django.core.cache import cache
        user_id = cache.get(f'password_reset_{reset_token}')

        if not user_id:
            return Response({'error': 'Invalid or expired reset token'},
                            status=status.HTTP_400_BAD_REQUEST)

        user = User.objects.filter(id=user_id).first()
        if not user:
            return Response({'error': 'User not found'},
                            status=status.HTTP_404_NOT_FOUND)

        # update password
        user.set_password(new_password)
        user.save()

        # delete reset token from cache
        cache.delete(f'password_reset_{reset_token}')

        return Response({'message': 'Password reset successfully. You can now login.'})

class UserListView(PaginatedListMixin, APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        users = User.objects.all().order_by('username')

        search = request.query_params.get('search')
        if search:
            users = users.filter(username__icontains=search)

        role = request.query_params.get('role')
        if role:
            users = users.filter(role=role)

        return self.paginated_response(users, UserSerializer, request)


class AssignRoleView(APIView):
    permission_classes = [IsAdmin]

    def patch(self, request, user_id):
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
    throttle_scope = 'login'

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

    @extend_schema(
            request=UserSerializer(partial=True),
            responses={200: UserSerializer},
        )
    def patch(self, request):
        serializer = UserSerializer(request.user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class RestaurantStatusView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        now = timezone.localtime()
        current_day = now.weekday()
        current_time = now.time()

        hours = OperatingHours.objects.filter(day=current_day).first()
        if not hours or not hours.is_open:
            return Response({
                'is_open': False,
                'message': 'Restaurant is currently closed'
            })

        is_open = hours.open_time <= current_time <= hours.close_time
        return Response({
            'is_open': is_open,
            'open_time': hours.open_time,
            'close_time': hours.close_time,
            'message': 'Restaurant is open' if is_open else 'Restaurant is currently closed'
        })


class NotificationListView(PaginatedListMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # --- FIX 3: Close filter parentheses correctly ---
        notifications = Notification.objects.filter(
            user=request.user).order_by('-created_at')
        return self.paginated_response(
            notifications, NotificationSerializer, request)
    
    def patch(self, request):
        Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
        return Response({'message':'All notifications are read'})

class OperatingHoursView(APIView):
    permission_classes = [IsAdminOrReadOnly]

    def get(self, request):
        hours = OperatingHours.objects.all().order_by('day')
        data = []
        for h in hours:
            data.append({
                'day':h.get_day_display(),
                'open_time':h.open_time,
                'close_time':h.close_time,
                'is_open':h.is_open
            })
        return Response(data)

    def post(self, request):
        day = request.data.get('day')
        open_time = request.data.get('open_time')
        close_time = request.data.get('close_time')
        # Non-null on the model, so an omitted value has to fall back rather
        # than write None - posting hours without it used to be a 500.
        is_open = request.data.get('is_open', True)

        if day is None or not open_time or not close_time:
            return Response({'error':'All fields are required'},
                            status=status.HTTP_400_BAD_REQUEST)

        hours, created = OperatingHours.objects.update_or_create(
            day=day,
            defaults={
                'open_time': open_time,
                'close_time': close_time,
                'is_open': is_open
            }
        )
        return Response({
            'day': hours.get_day_display(),
            'open_time': hours.open_time,
            'close_time': hours.close_time,
            'is_open': hours.is_open
        },status= status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    
