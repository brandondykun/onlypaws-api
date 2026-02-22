"""
Admin configuration for user app.
"""
from django.contrib import admin
from .models import (
    User,
    AuthProvider,
    VerifyEmailToken,
    ResetPasswordToken,
    PendingEmailChange,
)


@admin.register(AuthProvider)
class AuthProviderAdmin(admin.ModelAdmin):
    list_display = ("user", "provider", "external_id", "created_at")
    list_filter = ("provider",)
    search_fields = ("user__email", "external_id")
    raw_id_fields = ("user",)
    readonly_fields = ("created_at", "updated_at")


admin.site.register(User)
admin.site.register(VerifyEmailToken)
admin.site.register(ResetPasswordToken)
admin.site.register(PendingEmailChange)
