"""
Admin configuration for user app.
"""

from django.contrib import admin
from unfold.admin import ModelAdmin
from .models import (
    User,
    AuthProvider,
    VerifyEmailToken,
    ResetPasswordToken,
    PendingEmailChange,
    PendingAccountDeletion,
)


@admin.register(AuthProvider)
class AuthProviderAdmin(ModelAdmin):
    list_display = ("user", "provider", "external_id", "created_at")
    list_filter = ("provider",)
    search_fields = ("user__email", "external_id")
    raw_id_fields = ("user",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(User)
class UserAdmin(ModelAdmin):
    list_display = (
        "id",
        "email",
        "is_active",
        "is_staff",
        "is_superuser",
        "is_email_verified",
        "regular_profile_onboarding_completed",
        "business_profile_onboarding_completed",
    )
    list_filter = (
        "is_active",
        "is_staff",
        "is_superuser",
        "is_email_verified",
        "regular_profile_onboarding_completed",
        "business_profile_onboarding_completed",
    )
    search_fields = ("email",)
    ordering = ("-id",)
    readonly_fields = ("last_login", "created_at")


@admin.register(VerifyEmailToken)
class VerifyEmailTokenAdmin(ModelAdmin):
    list_display = ("user", "token", "created_at")
    search_fields = ("user__email", "token")
    readonly_fields = ("created_at",)
    raw_id_fields = ("user",)
    ordering = ("-created_at",)


@admin.register(ResetPasswordToken)
class ResetPasswordTokenAdmin(ModelAdmin):
    list_display = ("user", "token", "created_at")
    search_fields = ("user__email", "token")
    readonly_fields = ("created_at",)
    raw_id_fields = ("user",)
    ordering = ("-created_at",)


@admin.register(PendingEmailChange)
class PendingEmailChangeAdmin(ModelAdmin):
    list_display = ("user", "new_email", "verification_token", "created_at")
    search_fields = ("user__email", "new_email", "verification_token")
    readonly_fields = ("created_at",)
    raw_id_fields = ("user",)
    ordering = ("-created_at",)


@admin.register(PendingAccountDeletion)
class PendingAccountDeletionAdmin(ModelAdmin):
    list_display = ("user", "created_at", "scheduled_deletion_at", "days_remaining", "is_due")
    search_fields = ("user__email",)
    readonly_fields = ("created_at", "scheduled_deletion_at", "days_remaining", "is_due")
    raw_id_fields = ("user",)
    ordering = ("-created_at",)

    @admin.display(description="Scheduled Deletion At")
    def scheduled_deletion_at(self, obj):
        return obj.scheduled_deletion_at

    @admin.display(description="Days Remaining")
    def days_remaining(self, obj):
        return obj.days_remaining

    @admin.display(description="Is Due", boolean=True)
    def is_due(self, obj):
        return obj.is_due
