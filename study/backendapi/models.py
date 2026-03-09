from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra):
        if not email:
            raise ValueError('Email is required')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra):
        extra.setdefault('is_staff', True)
        extra.setdefault('is_superuser', True)
        return self.create_user(email, password, **extra)


class User(AbstractUser):
    username = None
    email = models.EmailField(unique=True)
    name = models.CharField(max_length=255, blank=True)

    google_access_token = models.TextField(null=True, blank=True)
    google_refresh_token = models.TextField(null=True, blank=True)

    study_start = models.TimeField(null=True, blank=True)
    study_end = models.TimeField(null=True, blank=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    objects = UserManager()

    def __str__(self):
        return self.email

    @property
    def google_connected(self):
        return bool(self.google_access_token)


class Assignment(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='assignments')
    title = models.CharField(max_length=500)
    course = models.CharField(max_length=500, blank=True)
    due_date = models.DateTimeField(null=True, blank=True)
    description = models.TextField(blank=True)

    # AI analysis fields
    estimated_hours = models.FloatField(null=True, blank=True)
    difficulty = models.IntegerField(null=True, blank=True)
    importance = models.IntegerField(null=True, blank=True)
    urgency = models.IntegerField(null=True, blank=True)
    recommended_session_minutes = models.IntegerField(null=True, blank=True)
    num_sessions = models.IntegerField(null=True, blank=True)
    start_days_before_due = models.IntegerField(null=True, blank=True)

    class Meta:
        ordering = ['due_date']

    def __str__(self):
        return self.title
