from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, Hall, Booking

# 1. Customizing how Users look in the dashboard
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'role', 'department', 'email')
    list_filter = ('role', 'department')
    fieldsets = UserAdmin.fieldsets + (
        ('Custom Roles', {'fields': ('role', 'department')}),
    )

# 2. Customizing how Halls look
class HallAdmin(admin.ModelAdmin):
    list_display = ('name', 'department', 'capacity', 'admin')
    list_filter = ('department',)

# 3. Customizing how Bookings look
class BookingAdmin(admin.ModelAdmin):
    list_display = ('hall', 'user', 'date', 'start_time', 'end_time', 'status')
    list_filter = ('status', 'hall', 'date')
    search_fields = ('user__username', 'purpose')

# Registering them to the dashboard
admin.site.register(User, CustomUserAdmin)
admin.site.register(Hall, HallAdmin)
admin.site.register(Booking, BookingAdmin)