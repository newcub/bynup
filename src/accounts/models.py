from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.crypto import get_random_string
import uuid
from django.utils import timezone

class UserType(models.Model):
    """Different types of users in the system"""
    name = models.CharField(max_length=50, unique=True)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = "User Type"
        verbose_name_plural = "User Types"
    
    def __str__(self):
        return self.name

class UserProfile(models.Model):
    """Extended user profile with type information"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    user_type = models.ForeignKey(UserType, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Profile details
    phone = models.CharField(max_length=20, blank=True)
    company = models.CharField(max_length=100, blank=True)
    bio = models.TextField(blank=True)
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    
    # Email verification
    email_verified = models.BooleanField(default=False)
    verification_token = models.CharField(max_length=100, blank=True)
    verification_sent_at = models.DateTimeField(blank=True, null=True)
    
    # Additional fields
    date_of_birth = models.DateField(blank=True, null=True)
    website = models.URLField(blank=True)
    has_received_free_domain = models.BooleanField(
        default=False,
        help_text="Set to True when the user's first free domain is activated. Prevents double-claiming."
    )

    class Meta:
        verbose_name = "User Profile"
        verbose_name_plural = "User Profiles"
    
    def __str__(self):
        return f"{self.user.username} - {self.user_type.name}"
    
    def generate_verification_token(self):
        self.verification_token = get_random_string(50)
        self.verification_sent_at = timezone.now()
        self.save()
        return self.verification_token

class WebsiteUser(models.Model):
    """
    Users registered through specific published websites
    Provides isolation between different website user bases
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='website_memberships')
    website = models.ForeignKey('builder.PublishedPage', on_delete=models.CASCADE, related_name='registered_users')
    registered_at = models.DateTimeField(auto_now_add=True)
    
    # Website-specific user data
    website_specific_data = models.JSONField(default=dict, blank=True)
    
    # Status
    is_active = models.BooleanField(default=True)
    is_verified = models.BooleanField(default=False)
    verification_token = models.CharField(max_length=100, blank=True)
    
    # Roles for website-specific permissions
    ROLE_CHOICES = [
        ('member', 'Member'),
        ('subscriber', 'Subscriber'),
        ('customer', 'Customer'),
        ('admin', 'Website Admin'),
    ]
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='member')
    
    class Meta:
        unique_together = ['user', 'website']
        verbose_name = 'Website User'
        verbose_name_plural = 'Website Users'
        ordering = ['-registered_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.website.brand_name}"

class UserActivity(models.Model):
    """Track user activity across the platform"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='activities')
    activity_type = models.CharField(max_length=50)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(default=dict, blank=True)
    
    class Meta:
        ordering = ['-timestamp']
        verbose_name = "User Activity"
        verbose_name_plural = "User Activities"
    
    def __str__(self):
        return f"{self.user.username} - {self.activity_type} - {self.timestamp}"

# Signals
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        # Determine user type based on context or default to 'Website Owner'
        user_type, _ = UserType.objects.get_or_create(
            name='Website Owner', 
            defaults={'slug': 'website-owner', 'description': 'Users who build websites'}
        )
        UserProfile.objects.create(user=instance, user_type=user_type)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    if hasattr(instance, 'profile'):
        instance.profile.save()