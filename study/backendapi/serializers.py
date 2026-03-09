from django.contrib.auth import get_user_model
from rest_framework import serializers
from .models import Assignment

User = get_user_model()


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ('email', 'password', 'name')

    def create(self, validated_data):
        return User.objects.create_user(
            email=validated_data['email'],
            password=validated_data['password'],
            name=validated_data.get('name', ''),
        )


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'email', 'name', 'google_connected', 'study_start', 'study_end')
        read_only_fields = ('id', 'email', 'name', 'google_connected')


class AssignmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Assignment
        fields = (
            'id', 'title', 'course', 'due_date', 'description',
            'estimated_hours', 'difficulty', 'importance', 'urgency',
            'recommended_session_minutes', 'num_sessions', 'start_days_before_due',
        )
        read_only_fields = ('id',)
