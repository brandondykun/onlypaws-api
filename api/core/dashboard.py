from django.urls import reverse
from django.utils import timezone

from apps.feedback_app.models import Feedback
from apps.moderation_app.models import PostReport, ProfileReport
from apps.profile_app.models import Profile
from apps.user_app.models import User


def dashboard_callback(request, context):
    thirty_days_ago = timezone.now() - timezone.timedelta(days=30)

    context["kpi_metrics"] = [
        {
            "title": "Active Users",
            "metric": User.objects.filter(is_active=True).count(),
            "icon": "people",
        },
        {
            "title": "Active Profiles",
            "metric": Profile.objects.filter(is_active=True).count(),
            "icon": "pets",
        },
        {
            "title": "New Users (30 days)",
            "metric": User.objects.filter(created_at__gte=thirty_days_ago)
            .distinct()
            .count(),
            "icon": "person_add",
        },
    ]

    context["kpi_links"] = [
        {
            "title": "Pending Post Reports",
            "metric": PostReport.objects.filter(status="PENDING").count(),
            "icon": "flag",
            "link": reverse("admin:moderation_app_postreport_changelist")
            + "?status__exact=PENDING",
        },
        {
            "title": "Pending Profile Reports",
            "metric": ProfileReport.objects.filter(status="PENDING").count(),
            "icon": "flag",
            "link": reverse("admin:moderation_app_profilereport_changelist")
            + "?status__exact=PENDING",
        },
        {
            "title": "Open Feedback",
            "metric": Feedback.objects.filter(status="open").count(),
            "icon": "feedback",
            "link": reverse("admin:feedback_app_feedback_changelist")
            + "?status__exact=open",
        },
    ]

    return context
