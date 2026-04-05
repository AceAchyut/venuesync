from rest_framework import serializers
from .models import User, Hall, Booking

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'role', 'department', 'email']

class HallSerializer(serializers.ModelSerializer):
    admin_name = serializers.CharField(source='admin.username', read_only=True)

    class Meta:
        model = Hall
        fields = ['id', 'name', 'department', 'capacity', 'admin_name']

class BookingSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.username', read_only=True)
    hall_name = serializers.CharField(source='hall.name', read_only=True)

    class Meta:
        model = Booking
        fields = ['id', 'user', 'user_name', 'hall', 'hall_name', 'date', 'start_time', 'end_time', 'purpose', 'status', 'admin_note']