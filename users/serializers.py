from rest_framework import serializers
from users.models import User, Notification


class RegisterSerializer(serializers.ModelSerializer):
    username = serializers.CharField()
    email = serializers.EmailField()
    password = serializers.CharField(write_only= True)
    phone_number = serializers.CharField(required = False)
    role = serializers.ChoiceField(
        choices=['customer','kitchen','admin'],
        default =['customer']
    )

    class Meta:
        model = User
        fields = ['username','email', 'password','phone_number','role']

class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username','email','phone_number','role']
        read_only_fields = ['role']

    def validate_email(self, value):
        normalized = value.lower()
        qs = User.objects.filter(email__iexact=normalized)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError('user with this email already exists.')
        return normalized

class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ['id','message','is_read','created_at']

class AuthResponseSerializer(serializers.Serializer):
    """What register, login and Google sign-in all return."""

    access = serializers.CharField()
    refresh = serializers.CharField()
    user = UserSerializer()


class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()


class VerifyResetOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()
    code = serializers.CharField(max_length=6)


class ResetTokenSerializer(serializers.Serializer):
    message = serializers.CharField()
    reset_token = serializers.CharField()


class ResetPasswordSerializer(serializers.Serializer):
    reset_token = serializers.CharField()
    new_password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)


class GoogleOAuthSerializer(serializers.Serializer):
    code = serializers.CharField()
    redirect_url = serializers.CharField(required=False)


class AssignRoleSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=['customer', 'kitchen', 'admin'])


class RestaurantStatusSerializer(serializers.Serializer):
    is_open = serializers.BooleanField()
    message = serializers.CharField()
    open_time = serializers.TimeField(required=False)
    close_time = serializers.TimeField(required=False)


class OperatingHoursSerializer(serializers.Serializer):
    day = serializers.CharField()
    open_time = serializers.TimeField()
    close_time = serializers.TimeField()
    is_open = serializers.BooleanField(required=False, default=True)
