import heapq
import secrets
import urllib.parse
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.conf import settings
from django.contrib.auth import get_user_model
from django.http import HttpResponseRedirect
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken, AccessToken

import json
from openai import OpenAI

from .serializers import RegisterSerializer, UserSerializer, AssignmentSerializer
from .models import Assignment


def _analyze_assignment(assignment, user):
    """Run AI analysis on an assignment and save results. Silently skips on error."""
    client = OpenAI(api_key=settings.OPENAI_API_KEY)

    study_window = ''
    if user.study_start and user.study_end:
        study_window = f"The student is available to study between {user.study_start.strftime('%H:%M')} and {user.study_end.strftime('%H:%M')}."

    due = assignment.due_date.strftime('%Y-%m-%d %H:%M') if assignment.due_date else 'unknown'

    prompt = f"""You are an academic planning assistant. Analyze the following assignment and return a JSON object with exactly these fields:
- estimated_hours (float): total estimated hours to complete. make sure this is an accurate estimate as AI models tend to overestimate the time it takes to do an academic task. No task, unless it is exam preperation should take longer than 5 hours. Most small assignments such as labs or classwork take at most 1 hours. Assignments such as projects, exams, or assessments should take longer, even up to 10 hours
- difficulty (int 1-10): how difficult the assignment is
- importance (int 1-10): how important it is to the course grade
- urgency (int 1-10): how urgent given the due date
- recommended_session_minutes (int): ideal length of a single study session in minutes
- num_sessions (int): recommended number of sessions to complete the work
- start_days_before_due (int): how many days before the due date the student should start

Assignment title: {assignment.title}
Course: {assignment.course or 'Unknown'}
Due date: {due}
Description: {assignment.description or 'None'}
{study_window}

Respond with only the JSON object, no explanation."""

    try:
        response = client.chat.completions.create(
            model='gpt-4o-mini',
            response_format={'type': 'json_object'},
            messages=[{'role': 'user', 'content': prompt}],
        )
        data = json.loads(response.choices[0].message.content)
    except Exception:
        return

    assignment.estimated_hours = data.get('estimated_hours')
    assignment.difficulty = data.get('difficulty')
    assignment.importance = data.get('importance')
    assignment.urgency = data.get('urgency')
    assignment.recommended_session_minutes = data.get('recommended_session_minutes')
    assignment.num_sessions = data.get('num_sessions')
    assignment.start_days_before_due = data.get('start_days_before_due')
    assignment.save()

User = get_user_model()

GOOGLE_AUTH_URL = 'https://accounts.google.com/o/oauth2/v2/auth'
GOOGLE_TOKEN_URL = 'https://oauth2.googleapis.com/token'
GOOGLE_CALENDAR_URL = 'https://www.googleapis.com/calendar/v3/calendars/primary/events'


def tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }


# POST /api/auth/register/
class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            return Response({
                'user': UserSerializer(user).data,
                **tokens_for_user(user),
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# POST /api/auth/login/
class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get('email', '').strip().lower()
        password = request.data.get('password', '')
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({'error': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)
        if not user.check_password(password):
            return Response({'error': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)
        return Response({
            'user': UserSerializer(user).data,
            **tokens_for_user(user),
        })


# GET + PATCH /api/auth/me/
class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)

    def patch(self, request):
        from datetime import time as dt_time
        start_str = request.data.get('study_start')
        end_str = request.data.get('study_end')

        if not start_str or not end_str:
            return Response({'error': 'study_start and study_end are required'}, status=400)

        try:
            start = dt_time.fromisoformat(start_str)
            end = dt_time.fromisoformat(end_str)
        except ValueError:
            return Response({'error': 'Invalid time format. Use HH:MM'}, status=400)

        if start >= end:
            return Response({'error': 'Start time must be before end time'}, status=400)

        request.user.study_start = start
        request.user.study_end = end
        request.user.save(update_fields=['study_start', 'study_end'])
        return Response(UserSerializer(request.user).data)


# GET /api/auth/google/?token=<access_token>
# Reads JWT from query param (browser redirects can't send headers), validates it,
# then redirects to Google OAuth consent screen with user PK encoded in state.
class GoogleLoginView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:5173')
        raw_token = request.GET.get('token', '')
        try:
            decoded = AccessToken(raw_token)
            user_id = decoded['user_id']
            user = User.objects.get(pk=user_id)
        except Exception:
            return HttpResponseRedirect(f'{frontend_url}/?google_error=invalid_token')

        state = f"{user.pk}:{secrets.token_hex(16)}"
        params = {
            'client_id': settings.GOOGLE_CLIENT_ID,
            'redirect_uri': settings.GOOGLE_REDIRECT_URI,
            'response_type': 'code',
            'scope': 'openid email profile https://www.googleapis.com/auth/calendar.events',
            'access_type': 'offline',
            'prompt': 'consent',
            'state': state,
        }
        url = GOOGLE_AUTH_URL + '?' + urllib.parse.urlencode(params)
        return HttpResponseRedirect(url)


# GET /api/auth/google/callback/
@method_decorator(csrf_exempt, name='dispatch')
class GoogleCallbackView(View):
    def get(self, request):
        frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:5173')
        code = request.GET.get('code')
        error = request.GET.get('error')
        state = request.GET.get('state', '')

        if error or not code:
            return HttpResponseRedirect(f'{frontend_url}/?google_error={error or "no_code"}')

        try:
            user_pk = int(state.split(':')[0])
            user = User.objects.get(pk=user_pk)
        except (ValueError, IndexError, User.DoesNotExist):
            return HttpResponseRedirect(f'{frontend_url}/?google_error=invalid_state')

        token_response = requests.post(GOOGLE_TOKEN_URL, data={
            'code': code,
            'client_id': settings.GOOGLE_CLIENT_ID,
            'client_secret': settings.GOOGLE_CLIENT_SECRET,
            'redirect_uri': settings.GOOGLE_REDIRECT_URI,
            'grant_type': 'authorization_code',
        })
        token_data = token_response.json()

        access_token = token_data.get('access_token')
        refresh_token = token_data.get('refresh_token')

        if not access_token:
            return HttpResponseRedirect(f'{frontend_url}/?google_error=token_exchange_failed')

        user.google_access_token = access_token
        if refresh_token:
            user.google_refresh_token = refresh_token
        user.save(update_fields=['google_access_token', 'google_refresh_token'])

        return HttpResponseRedirect(f'{frontend_url}/?google_linked=true')


# GET + POST /api/calendar/events/
class CalendarEventsView(APIView):
    permission_classes = [IsAuthenticated]

    def _refresh_google_token(self, user):
        if not user.google_refresh_token:
            return False
        resp = requests.post(GOOGLE_TOKEN_URL, data={
            'client_id': settings.GOOGLE_CLIENT_ID,
            'client_secret': settings.GOOGLE_CLIENT_SECRET,
            'refresh_token': user.google_refresh_token,
            'grant_type': 'refresh_token',
        })
        new_token = resp.json().get('access_token')
        if new_token:
            user.google_access_token = new_token
            user.save(update_fields=['google_access_token'])
            return True
        return False

    def post(self, request):
        user = request.user
        if not user.google_connected:
            return Response({'error': 'Google account not connected'}, status=status.HTTP_403_FORBIDDEN)

        summary = request.data.get('summary', '').strip()
        start_datetime = request.data.get('start_datetime')
        end_datetime = request.data.get('end_datetime')
        description = request.data.get('description', '')
        timezone = request.data.get('timezone', 'UTC')

        if not all([summary, start_datetime, end_datetime]):
            return Response({'error': 'summary, start_datetime, and end_datetime are required'}, status=400)

        try:
            tz = ZoneInfo(timezone)
        except ZoneInfoNotFoundError:
            tz = ZoneInfo('UTC')

        def to_rfc3339(dt_str):
            naive = datetime.strptime(dt_str, '%Y-%m-%dT%H:%M')
            return naive.replace(tzinfo=tz).isoformat()

        try:
            start_rfc3339 = to_rfc3339(start_datetime)
            end_rfc3339 = to_rfc3339(end_datetime)
        except ValueError as e:
            return Response({'error': f'Invalid datetime format: {e}'}, status=400)

        event_body = {
            'summary': summary,
            'description': description,
            'start': {'dateTime': start_rfc3339},
            'end': {'dateTime': end_rfc3339},
        }

        response = requests.post(
            GOOGLE_CALENDAR_URL,
            headers={'Authorization': f'Bearer {user.google_access_token}', 'Content-Type': 'application/json'},
            json=event_body,
        )

        if response.status_code in (200, 201):
            return Response({'event': response.json()}, status=201)
        return Response({'error': response.json()}, status=response.status_code)


# GET /api/assignments/
class AssignmentListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        assignments = Assignment.objects.filter(user=request.user)
        return Response(AssignmentSerializer(assignments, many=True).data)


# DELETE /api/assignments/all/
class AssignmentDeleteAllView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request):
        Assignment.objects.filter(user=request.user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# POST /api/assignments/upload-ics/
class ICSUploadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from icalendar import Calendar

        ics_file = request.FILES.get('file')
        if not ics_file:
            return Response({'error': 'No file provided'}, status=400)

        try:
            cal = Calendar.from_ical(ics_file.read())
        except Exception:
            return Response({'error': 'Invalid .ics file'}, status=400)

        import re
        existing_titles = set(
            Assignment.objects.filter(user=request.user).values_list('title', flat=True)
        )

        created = []
        for component in cal.walk():
            if component.name != 'VEVENT':
                continue

            title = str(component.get('SUMMARY', '')).strip() or '(No title)'
            if title in existing_titles:
                continue

            description = str(component.get('DESCRIPTION', '')).strip()

            match = re.search(r'\[([A-Z]+\s+\d{3})\b', title)
            course = match.group(1) if match else ''

            dtstart = component.get('DTSTART')
            due_date = None
            if dtstart:
                val = dtstart.dt
                if hasattr(val, 'hour'):
                    due_date = val if val.tzinfo else val.replace(tzinfo=ZoneInfo('UTC'))
                else:
                    due_date = datetime(val.year, val.month, val.day, tzinfo=ZoneInfo('UTC'))

            assignment = Assignment.objects.create(
                user=request.user,
                title=title,
                course=course,
                due_date=due_date,
                description=description,
            )
            existing_titles.add(title)
            _analyze_assignment(assignment, request.user)
            created.append(assignment)

        return Response(
            AssignmentSerializer(created, many=True).data,
            status=status.HTTP_201_CREATED,
        )


# POST /api/assignments/<id>/analyze/
class AssignmentAnalyzeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, assignment_id):
        try:
            assignment = Assignment.objects.get(pk=assignment_id, user=request.user)
        except Assignment.DoesNotExist:
            return Response({'error': 'Assignment not found'}, status=404)

        _analyze_assignment(assignment, request.user)
        return Response(AssignmentSerializer(assignment).data)


# POST /api/schedule/
class ScheduleView(APIView):
    permission_classes = [IsAuthenticated]

    def _post_event(self, user, event_body):
        headers = {
            'Authorization': f'Bearer {user.google_access_token}',
            'Content-Type': 'application/json',
        }
        resp = requests.post(GOOGLE_CALENDAR_URL, headers=headers, json=event_body)
        if resp.status_code == 401 and user.google_refresh_token:
            token_resp = requests.post(GOOGLE_TOKEN_URL, data={
                'client_id': settings.GOOGLE_CLIENT_ID,
                'client_secret': settings.GOOGLE_CLIENT_SECRET,
                'refresh_token': user.google_refresh_token,
                'grant_type': 'refresh_token',
            })
            new_token = token_resp.json().get('access_token')
            if new_token:
                user.google_access_token = new_token
                user.save(update_fields=['google_access_token'])
                headers['Authorization'] = f'Bearer {new_token}'
                resp = requests.post(GOOGLE_CALENDAR_URL, headers=headers, json=event_body)
        return resp

    def post(self, request):
        user = request.user

        if not user.google_connected:
            return Response({'error': 'Google account not connected'}, status=403)
        if not user.study_start or not user.study_end:
            return Response({'error': 'Study window not set. Configure your study hours first.'}, status=400)

        timezone_str = request.data.get('timezone', 'UTC')
        try:
            tz = ZoneInfo(timezone_str)
        except ZoneInfoNotFoundError:
            tz = ZoneInfo('UTC')

        assignments = list(Assignment.objects.filter(
            user=user,
            due_date__isnull=False,
            num_sessions__isnull=False,
            recommended_session_minutes__isnull=False,
            start_days_before_due__isnull=False,
            urgency__isnull=False,
        ))

        if not assignments:
            return Response({'scheduled': [], 'message': 'No analyzed assignments to schedule'})

        today = datetime.now(tz).date()

        # Build per-assignment scheduling state
        items = []
        for a in assignments:
            due = a.due_date.astimezone(tz).date()
            start = due - timedelta(days=a.start_days_before_due)
            items.append({
                'assignment': a,
                'urgency': float(a.urgency),
                'sessions_remaining': a.num_sessions,
                'session_minutes': a.recommended_session_minutes,
                'start_date': start,
                'due_date': due,
            })

        study_start_min = user.study_start.hour * 60 + user.study_start.minute
        study_end_min = user.study_end.hour * 60 + user.study_end.minute

        # pending: items not yet added to the heap (sorted by start_date)
        pending = sorted(items, key=lambda x: x['start_date'])
        heap = []   # entries: (-urgency, counter, item)
        counter = 0

        earliest = min(max(today, i['start_date']) for i in items)
        latest = max(i['due_date'] for i in items)
        current_date = earliest

        scheduled = []

        while current_date <= latest:
            # Activate assignments whose scheduling window has opened
            still_pending = []
            for item in pending:
                if item['start_date'] <= current_date:
                    heapq.heappush(heap, (-item['urgency'], counter, item))
                    counter += 1
                else:
                    still_pending.append(item)
            pending = still_pending

            # Fill today's study window slot by slot
            slot_min = study_start_min
            while heap:
                neg_urg, _, item = heap[0]  # peek

                if slot_min + item['session_minutes'] > study_end_min:
                    break  # no room left today

                heapq.heappop(heap)

                # Skip stale/expired items
                if item['sessions_remaining'] <= 0 or current_date > item['due_date']:
                    continue

                h, m = divmod(slot_min, 60)
                session_start = datetime(current_date.year, current_date.month, current_date.day, h, m, tzinfo=tz)
                session_end = session_start + timedelta(minutes=item['session_minutes'])

                session_num = item['assignment'].num_sessions - item['sessions_remaining'] + 1
                event_body = {
                    'summary': f"Study: {item['assignment'].title} (Session {session_num}/{item['assignment'].num_sessions})",
                    'description': f"Course: {item['assignment'].course or 'Unknown'}\nDue: {item['due_date']}",
                    'start': {'dateTime': session_start.isoformat()},
                    'end': {'dateTime': session_end.isoformat()},
                }

                resp = self._post_event(user, event_body)
                if resp.status_code in (200, 201):
                    scheduled.append(resp.json())
                    item['sessions_remaining'] -= 1
                    item['urgency'] *= 2 / 3

                slot_min += item['session_minutes']

                if item['sessions_remaining'] > 0:
                    heapq.heappush(heap, (-item['urgency'], counter, item))
                    counter += 1

            current_date += timedelta(days=1)

            if not heap and not pending:
                break

        return Response({'scheduled': scheduled, 'count': len(scheduled)})
