from django.db import models
from django.contrib.auth.models import AbstractUser

# 1. Custom User Model (Handles Roles and Departments)
class User(AbstractUser):
    ROLE_CHOICES = (
        ('superadmin', 'Super Admin'),
        ('halladmin', 'Hall Admin'),
        ('member', 'Committee Member'),
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='member')
    department = models.CharField(max_length=100, null=True, blank=True)

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"

# 2. Hall Model (The 4 Seminar Halls)
class Hall(models.Model):
    name = models.CharField(max_length=100) # e.g., "Vinay Kore Hall"
    department = models.CharField(max_length=100)
    capacity = models.IntegerField(default=100)
    admin = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, limit_choices_to={'role': 'halladmin'})

    def __str__(self):
        return self.name

# 3. Booking Model (The Request Engine)
class Booking(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bookings')
    hall = models.ForeignKey(Hall, on_delete=models.CASCADE)
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    purpose = models.TextField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    admin_note = models.TextField(null=True, blank=True) # Reason for rejection/approval

    def __str__(self):
        return f"{self.hall.name} booked by {self.user.username} on {self.date}"