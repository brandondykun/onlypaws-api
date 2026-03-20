from django.contrib import admin
from .models import Feedback, FeedbackComment
from unfold.admin import ModelAdmin


class FeedbackCommentInline(admin.TabularInline):
    model = FeedbackComment
    extra = 1
    readonly_fields = ("created_at",)
    fields = ("author", "content", "is_internal", "created_at")

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "author":
            kwargs["queryset"] = db_field.related_model.objects.filter(is_staff=True)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(Feedback)
class FeedbackAdmin(ModelAdmin):
    list_display = (
        "id",
        "title",
        "ticket_type",
        "status",
        "priority",
        "reporter",
        "assignee",
        "created_at",
    )
    list_filter = ("ticket_type", "status", "priority", "created_at")
    search_fields = ("title", "description", "reporter__email")
    readonly_fields = ("created_at", "updated_at")
    list_editable = ("status", "priority", "assignee")
    inlines = [FeedbackCommentInline]
    ordering = ("-created_at",)

    fieldsets = (
        ("Ticket Information", {"fields": ("title", "description", "ticket_type")}),
        ("Status & Priority", {"fields": ("status", "priority", "assignee")}),
        ("Reporter Information", {"fields": ("reporter",)}),
        (
            "App Context",
            {"fields": ("app_version", "device_info"), "classes": ("collapse",)},
        ),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )


@admin.register(FeedbackComment)
class FeedbackCommentAdmin(ModelAdmin):
    list_display = ("id", "ticket", "author", "is_internal", "created_at")
    list_filter = ("is_internal", "created_at")
    search_fields = ("content", "ticket__title", "author__email")
    readonly_fields = ("created_at",)
    ordering = ("-created_at",)

    fieldsets = (
        (
            "Comment Information",
            {"fields": ("ticket", "author", "content", "is_internal")},
        ),
        ("Timestamps", {"fields": ("created_at",)}),
    )
