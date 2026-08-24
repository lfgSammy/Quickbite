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
    user = UserSerializer(read_only= True)
    class Meta:
        model = Notification
        fields = ['id','message','is_read','created_at']