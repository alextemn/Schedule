from django.urls import path
from .views import GoogleLoginView, GoogleCallbackView, CalendarEventsView, DeleteCalendarEventView

urlpatterns = [
    path('auth/google/', GoogleLoginView.as_view(), name='google-login'),
    path('auth/google/callback/', GoogleCallbackView.as_view(), name='google-callback'),
    path('calendar/events/', CalendarEventsView.as_view(), name='calendar-events'),
    path('calendar/events/<str:event_id>/', DeleteCalendarEventView.as_view(), name='delete-calendar-event'),
]
