import json
import urllib.parse
import requests
from datetime import datetime, timezone as dt_timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from django.conf import settings
from django.http import HttpResponseRedirect, JsonResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator


GOOGLE_AUTH_URL = 'https://accounts.google.com/o/oauth2/v2/auth'
GOOGLE_TOKEN_URL = 'https://oauth2.googleapis.com/token'
GOOGLE_USERINFO_URL = 'https://www.googleapis.com/oauth2/v3/userinfo'
GOOGLE_CALENDAR_URL = 'https://www.googleapis.com/calendar/v3/calendars/primary/events'
FRONTEND_URL = 'http://localhost:5173'


class GoogleLoginView(View):
    def get(self, request):
        params = {
            'client_id': settings.GOOGLE_CLIENT_ID,
            'redirect_uri': settings.GOOGLE_REDIRECT_URI,
            'response_type': 'code',
            'scope': 'openid email profile https://www.googleapis.com/auth/calendar.events',
            'access_type': 'offline',
            'prompt': 'consent',
        }
        url = GOOGLE_AUTH_URL + '?' + urllib.parse.urlencode(params)
        return HttpResponseRedirect(url)


class GoogleCallbackView(View):
    def get(self, request):
        code = request.GET.get('code')
        error = request.GET.get('error')

        if error or not code:
            return HttpResponseRedirect(f'{FRONTEND_URL}?auth_error={error or "no_code"}')

        token_response = requests.post(GOOGLE_TOKEN_URL, data={
            'code': code,
            'client_id': settings.GOOGLE_CLIENT_ID,
            'client_secret': settings.GOOGLE_CLIENT_SECRET,
            'redirect_uri': settings.GOOGLE_REDIRECT_URI,
            'grant_type': 'authorization_code',
        })
        token_data = token_response.json()

        access_token = token_data.get('access_token')
        if not access_token:
            return HttpResponseRedirect(f'{FRONTEND_URL}?auth_error=token_exchange_failed')

        userinfo_response = requests.get(
            GOOGLE_USERINFO_URL,
            headers={'Authorization': f'Bearer {access_token}'},
        )
        user_info = userinfo_response.json()
        user_info['access_token'] = access_token

        encoded = urllib.parse.quote(json.dumps(user_info))
        return HttpResponseRedirect(f'{FRONTEND_URL}?user={encoded}')


@method_decorator(csrf_exempt, name='dispatch')
class CalendarEventsView(View):
    def get(self, request):
        access_token = request.GET.get('access_token')
        if not access_token:
            return JsonResponse({'error': 'access_token is required'}, status=400)

        now = datetime.now(dt_timezone.utc).isoformat()
        response = requests.get(
            GOOGLE_CALENDAR_URL,
            headers={'Authorization': f'Bearer {access_token}'},
            params={
                'timeMin': now,
                'maxResults': 20,
                'orderBy': 'startTime',
                'singleEvents': 'true',
            },
        )

        if response.status_code == 200:
            return JsonResponse({'events': response.json().get('items', [])})
        else:
            return JsonResponse({'error': response.json()}, status=response.status_code)

    def post(self, request):
        try:
            body = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        access_token = body.get('access_token')
        summary = body.get('summary', '').strip()
        start_datetime = body.get('start_datetime')
        end_datetime = body.get('end_datetime')
        description = body.get('description', '')
        timezone = body.get('timezone', 'UTC')

        if not all([access_token, summary, start_datetime, end_datetime]):
            return JsonResponse({'error': 'access_token, summary, start_datetime, and end_datetime are required'}, status=400)

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
            return JsonResponse({'error': f'Invalid datetime format: {e}'}, status=400)

        event_body = {
            'summary': summary,
            'description': description,
            'start': {'dateTime': start_rfc3339},
            'end': {'dateTime': end_rfc3339},
        }

        response = requests.post(
            GOOGLE_CALENDAR_URL,
            headers={
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json',
            },
            json=event_body,
        )

        if response.status_code in (200, 201):
            event = response.json()
            print('Created calendar event:', event)
            return JsonResponse({'event': event}, status=201)
        else:
            return JsonResponse({'error': response.json()}, status=response.status_code)


@method_decorator(csrf_exempt, name='dispatch')
class DeleteCalendarEventView(View):
    def delete(self, request, event_id):
        try:
            body = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        access_token = body.get('access_token')
        if not access_token:
            return JsonResponse({'error': 'access_token is required'}, status=400)

        response = requests.delete(
            f'{GOOGLE_CALENDAR_URL}/{event_id}',
            headers={'Authorization': f'Bearer {access_token}'},
        )

        if response.status_code == 204:
            print(f'Deleted calendar event: {event_id}')
            return JsonResponse({'deleted': event_id})
        else:
            return JsonResponse({'error': response.json()}, status=response.status_code)
