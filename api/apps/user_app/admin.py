"""
Admin configuration for user app.
"""
from django.contrib import admin
from .models import (
    User,
    VerifyEmailToken,
    ResetPasswordToken,
    PendingEmailChange,
)

admin.site.register(User)
admin.site.register(VerifyEmailToken)
admin.site.register(ResetPasswordToken)
admin.site.register(PendingEmailChange)
