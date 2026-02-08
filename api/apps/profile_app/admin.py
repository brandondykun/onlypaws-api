from django.contrib import admin
from .models import Profile, RegularProfile, BusinessProfile, ProfileImage, ProfileImageScaled, PetType, Address


@admin.register(PetType)
class PetTypeAdmin(admin.ModelAdmin):
    list_display = ['id', 'name']
    search_fields = ['name']
    ordering = ['name']


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ['id', 'street_address', 'city', 'state', 'country']
    search_fields = ['street_address', 'city', 'state', 'country']
    list_filter = ['country', 'state']


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ['id', 'username', 'user', 'is_active', 'get_profile_type', 'created_at']
    search_fields = ['username', 'user__email']
    list_filter = ['is_active', 'created_at']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']

    def get_profile_type(self, obj):
        return obj.get_profile_type()
    get_profile_type.short_description = 'Profile Type'


@admin.register(RegularProfile)
class RegularProfileAdmin(admin.ModelAdmin):
    list_display = ['id', 'username', 'name', 'pet_type', 'user_email', 'created_at']
    search_fields = ['profile_ptr__username', 'name', 'profile_ptr__user__email']
    list_filter = ['pet_type', 'profile_ptr__created_at']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-profile_ptr__created_at']

    def username(self, obj):
        return obj.profile_ptr.username

    def user_email(self, obj):
        return obj.profile_ptr.user.email
    user_email.short_description = 'User Email'

    def created_at(self, obj):
        return obj.profile_ptr.created_at

    def updated_at(self, obj):
        return obj.profile_ptr.updated_at


@admin.register(BusinessProfile)
class BusinessProfileAdmin(admin.ModelAdmin):
    list_display = ['id', 'username', 'business_name', 'business_category', 'verified', 'subscription_tier', 'user_email', 'created_at']
    search_fields = ['profile_ptr__username', 'business_name', 'profile_ptr__user__email']
    list_filter = ['business_category', 'verified', 'subscription_tier', 'profile_ptr__created_at']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-profile_ptr__created_at']

    def username(self, obj):
        return obj.profile_ptr.username

    def user_email(self, obj):
        return obj.profile_ptr.user.email
    user_email.short_description = 'User Email'

    def created_at(self, obj):
        return obj.profile_ptr.created_at

    def updated_at(self, obj):
        return obj.profile_ptr.updated_at


@admin.register(ProfileImage)
class ProfileImageAdmin(admin.ModelAdmin):
    list_display = ['id', 'profile', 'image', 'processing_status', 'created_at', 'updated_at']
    search_fields = ['profile__username']
    list_filter = ['processing_status']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']


@admin.register(ProfileImageScaled)
class ProfileImageScaledAdmin(admin.ModelAdmin):
    list_display = ['id', 'profile_image', 'scale', 'width', 'height', 'created_at']
    list_filter = ['scale']
    search_fields = ['profile_image__profile__username']
    ordering = ['profile_image', 'scale']

