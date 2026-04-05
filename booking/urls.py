from django.urls import path, include
from rest_framework.routers import DefaultRouter

# 1. We import ONLY the exact functions we need, including ai_parse_booking!
from .views import (
    HallViewSet, 
    BookingViewSet, 
    login_view, 
    dashboard_view, 
    logout_view, 
    update_status,
    ai_parse_booking  # <--- The correct name is imported here
)

router = DefaultRouter()
router.register(r'halls', HallViewSet)
router.register(r'bookings', BookingViewSet)

urlpatterns = [
    path('api/', include(router.urls)),
    path('login/', login_view, name='login'),
    path('dashboard/', dashboard_view, name='dashboard'),
    path('logout/', logout_view, name='logout'),
    path('status/<int:booking_id>/<str:action>/', update_status, name='update_status'),
    
    # 2. We use the directly imported function here
    path('api/ai-parse/', ai_parse_booking, name='ai_parse'),
]