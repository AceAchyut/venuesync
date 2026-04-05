from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from rest_framework import viewsets, status
from rest_framework.response import Response
from django.db.models import Q
from .models import Hall, Booking
from .serializers import HallSerializer, BookingSerializer
import re 
from google import genai
import json
from datetime import datetime, timedelta
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from groq import Groq
import os

# 1. API to simply list the Halls for the frontend
class HallViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Hall.objects.all()
    serializer_class = HallSerializer

# 2. API to handle Bookings and Conflict Detection
class BookingViewSet(viewsets.ModelViewSet):
    queryset = Booking.objects.all()
    serializer_class = BookingSerializer

    # Overriding the default creation method to add our custom logic
    def create(self, request, *args, **kwargs):
        hall_id = request.data.get('hall')
        date = request.data.get('date')
        start_time = request.data.get('start_time')
        end_time = request.data.get('end_time')

        # --- THE SMART CONFLICT DETECTION LOGIC 🔥 ---
        conflicts = Booking.objects.filter(
            hall_id=hall_id,
            date=date,
            status__in=['approved', 'pending']
        ).filter(
            Q(start_time__lt=end_time) & Q(end_time__gt=start_time)
        )

        if conflicts.exists():
            return Response(
                {"error": "Slot already booked! This hall has an approved or pending request for this time."},
                status=status.HTTP_400_BAD_REQUEST
            )

        return super().create(request, *args, **kwargs)


# ---------------------------------------------------------
# 3. Frontend Views 
# ---------------------------------------------------------

def login_view(request):
    error_message = None
    if request.method == 'POST':
        u = request.POST.get('username')
        p = request.POST.get('password')
        user = authenticate(request, username=u, password=p)
        
        if user is not None:
            login(request, user)
            return redirect('/dashboard/')
        else:
            error_message = "Invalid username or password. Please try again."

    return render(request, 'login.html', {'error': error_message})


@login_required(login_url='/login/')
def dashboard_view(request):
    user = request.user
    
    # 1. IF THE USER IS A HALL ADMIN
    if user.role == 'halladmin':
        try:
            # Find the hall this admin controls
            admin_hall = Hall.objects.get(admin=user)
            # Fetch all bookings for THEIR hall
            bookings = Booking.objects.filter(hall=admin_hall).order_by('-date', '-start_time')
        except Hall.DoesNotExist:
            admin_hall = None
            bookings = []
            
        return render(request, 'dashboard.html', {
            'is_admin': True,
            'hall': admin_hall,
            'bookings': bookings
        })
        
    # 2. IF THE USER IS A NORMAL MEMBER
    else:
        halls = Hall.objects.all()
        user_bookings = Booking.objects.filter(user=user).order_by('-date', '-start_time')
        return render(request, 'dashboard.html', {
            'is_admin': False,
            'halls': halls, 
            'bookings': user_bookings
        })


# 3. THE APPROVE/REJECT FUNCTION
@login_required(login_url='/login/')
def update_status(request, booking_id, action):
    if request.user.role == 'halladmin':
        booking = get_object_or_404(Booking, id=booking_id)
        
        if booking.hall.admin == request.user:
            if action == 'approve':
                booking.status = 'approved'
            elif action == 'reject':
                booking.status = 'rejected'
            booking.save()

            # --- SEND EMAIL TO USER ---
            if booking.user.email:
                send_mail(
                    subject=f'VenueSync: Booking {booking.status.capitalize()}',
                    message=f'Hello {booking.user.username},\n\nYour booking request for {booking.hall.name} on {booking.date} has been {booking.status}.\n\n- TKIET VenueSync System',
                    from_email=None, 
                    recipient_list=[booking.user.email],
                    fail_silently=True,
                )
            
    return redirect('/dashboard/')

# 4. THE LOGOUT FUNCTION
def logout_view(request):
    logout(request)
    return redirect('/login/')

# ---------------------------------------------------------
# 4. AI INTEGRATION WITH NEW GOOGLE GENAI LIBRARY
# ---------------------------------------------------------

# 1. Safely initialize the new client outside the function
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
@csrf_exempt
@login_required(login_url='/login/')
def ai_parse_booking(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            user_text = data.get('text')
            today_date = datetime.now().strftime("%Y-%m-%d")

            # 1. Get actual halls
            halls = Hall.objects.all()
            hall_context = "\n".join([f"- {h.name} (Capacity: {h.capacity})" for h in halls])
            if not hall_context:
                hall_context = "No halls currently in database."

            # 2. NEW: Get actual upcoming bookings!
            upcoming = Booking.objects.filter(status__in=['approved', 'pending'])
            schedule_context = "\n".join([
                f"- {b.hall.name} on {b.date} from {b.start_time} to {b.end_time}" 
                for b in upcoming
            ])
            if not schedule_context:
                schedule_context = "All halls are completely free. No events are scheduled right now."

            system_prompt = f"""
            You are an intelligent venue booking assistant for TKIET college. 
            Today's date is {today_date}.

            HERE ARE THE ONLY AVAILABLE HALLS:
            {hall_context}

            HERE IS THE CURRENT BOOKED SCHEDULE:
            {schedule_context}

            Extract the following details from the user's text and return ONLY a valid JSON object. 
            - "hall_keyword": The name of the hall they want. 
            - "date": Format YYYY-MM-DD. Calculate "tomorrow" or "next Monday" based on today's date.
            - "start_time": Format HH:MM (24-hour).
            - "end_time": Format HH:MM (24-hour). Assume 2 hours if not specified.
            - "purpose": A short title for the event.
            - "capacity_needed": Number of people if mentioned, otherwise null.
            - "ai_reply": A friendly response. 
                * RULE 1: If they ask about events or availability, look at the CURRENT BOOKED SCHEDULE above and tell them exactly what is booked or if it's free.
                * RULE 2: If they try to book a time that overlaps with the CURRENT BOOKED SCHEDULE, tell them it is already taken and suggest a different time.
                * RULE 3: If you are missing the Date, Time, or Purpose for a new booking, ask them for it.
            """

            # Call the Groq AI
            completion = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_text}
                ],
                temperature=0, 
                response_format={"type": "json_object"} 
            )
            
            try:
                ai_data = json.loads(completion.choices[0].message.content)
            except json.JSONDecodeError:
                return JsonResponse({'error': 'Please specify a hall, date, and time so I can book it for you!'}, status=400)
            
            # Find Hall
            best_hall = None
            if ai_data.get('hall_keyword'):
                best_hall = Hall.objects.filter(name__icontains=ai_data['hall_keyword']).first()
            
            # Check if it's just a chat, missing info, OR answering a schedule question!
            if not best_hall or not ai_data.get('date') or not ai_data.get('start_time'):
                return JsonResponse({
                    'is_incomplete': True, 
                    'message': ai_data.get('ai_reply', "Could you please specify the hall, date, and time you need?")
                })

            # Check Conflicts (Backend safety net)
            conflict = False
            if best_hall and ai_data.get('date') and ai_data.get('start_time'):
                conflict = Booking.objects.filter(
                    hall=best_hall, 
                    date=ai_data['date'], 
                    status__in=['approved', 'pending'],
                    start_time__lt=ai_data['end_time'], 
                    end_time__gt=ai_data['start_time']
                ).exists()

            return JsonResponse({
                'hall_id': best_hall.id if best_hall else None,
                'hall_name': best_hall.name if best_hall else None,
                'date': ai_data.get('date'),
                'start_time': ai_data.get('start_time'),
                'end_time': ai_data.get('end_time'),
                'purpose': ai_data.get('purpose'),
                'has_conflict': conflict,
                'message': "Wait, this hall is already booked!" if conflict else "Perfect! Extracted details."
            })

        except Exception as e:
            print("AI ERROR:", str(e)) 
            return JsonResponse({'error': str(e)}, status=400)