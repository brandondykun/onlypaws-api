from django.contrib import admin

from .models import TermsOfService, TermsAcceptance


@admin.register(TermsOfService)
class TermsOfServiceAdmin(admin.ModelAdmin):
    list_display = ("id", "version", "is_active", "created_at")
    list_filter = ("is_active", "created_at")
    search_fields = ("version", "content")
    readonly_fields = ("created_at",)


@admin.register(TermsAcceptance)
class TermsAcceptanceAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "terms", "accepted_at", "ip_address")
    list_filter = ("accepted_at", "terms")
    search_fields = ("user__email", "terms__version")
    readonly_fields = ("accepted_at",)
