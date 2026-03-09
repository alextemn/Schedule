from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import (
    RegisterView,
    LoginView,
    MeView,
    GoogleLoginView,
    GoogleCallbackView,
    CalendarEventsView,
    AssignmentListView,
    AssignmentDeleteAllView,
    ICSUploadView,
    AssignmentAnalyzeView,
)

urlpatterns = [
    path('auth/register/', RegisterView.as_view(), name='register'),
    path('auth/login/', LoginView.as_view(), name='login'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token-refresh'),
    path('auth/me/', MeView.as_view(), name='me'),
    path('auth/google/', GoogleLoginView.as_view(), name='google-login'),
    path('auth/google/callback/', GoogleCallbackView.as_view(), name='google-callback'),
    path('calendar/events/', CalendarEventsView.as_view(), name='calendar-events'),
    path('assignments/', AssignmentListView.as_view(), name='assignments'),
    path('assignments/all/', AssignmentDeleteAllView.as_view(), name='assignments-delete-all'),
    path('assignments/upload-ics/', ICSUploadView.as_view(), name='upload-ics'),
    path('assignments/<int:assignment_id>/analyze/', AssignmentAnalyzeView.as_view(), name='assignment-analyze'),
]
