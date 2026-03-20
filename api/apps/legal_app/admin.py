from django.contrib import admin
from django.contrib.admin import widgets
from unfold.admin import ModelAdmin

from .models import TermsOfService, TermsAcceptance


@admin.register(TermsOfService)
class TermsOfServiceAdmin(ModelAdmin):
    list_display = ("id", "version", "is_active", "created_at")
    list_filter = ("is_active", "created_at")
    search_fields = ("version", "content")
    readonly_fields = ("created_at",)

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if db_field.name == "content":
            kwargs["widget"] = widgets.AdminTextareaWidget(
                attrs={"style": "width: 100%;"}
            )
        return super().formfield_for_dbfield(db_field, request, **kwargs)


@admin.register(TermsAcceptance)
class TermsAcceptanceAdmin(ModelAdmin):
    list_display = ("id", "user", "terms", "accepted_at", "ip_address")
    list_filter = ("accepted_at", "terms")
    search_fields = ("user__email", "terms__version")
    readonly_fields = ("accepted_at",)
