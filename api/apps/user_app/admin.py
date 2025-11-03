"""
Admin configuration for user app.
"""
from django.contrib import admin
from .models import (
    User,
    Profile,
    RegularProfile,
    BusinessProfile,
    ProfileImage,
    PetType,
    Address,
    VerifyEmailToken,
    ResetPasswordToken,
    PendingEmailChange,
)

admin.site.register(User)
admin.site.register(Profile)
admin.site.register(RegularProfile)
admin.site.register(BusinessProfile)
admin.site.register(ProfileImage)
admin.site.register(PetType)
admin.site.register(Address)
admin.site.register(VerifyEmailToken)
admin.site.register(ResetPasswordToken)
admin.site.register(PendingEmailChange)

