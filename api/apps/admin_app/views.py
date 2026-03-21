"""
Views for the admin dashboard..
"""

import calendar
import datetime

from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from django.contrib.auth import get_user_model
from django.db.models import Count
from django.db.models.functions import TruncMonth
from django.utils import timezone
from drf_spectacular.utils import extend_schema, OpenApiParameter


User = get_user_model()


class AdminTimeSeriesView(APIView):
    """
    Base view for time-series chart endpoints.

    Subclasses must define:
    - model: The Django model to query
    - date_field: The DateTimeField to truncate by month
    - annotation_name: Name for the count annotation (default: 'count')
    """

    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]
    model = None
    date_field = None
    annotation_name = "count"

    def get_queryset(self):
        return self.model.objects.all()

    @staticmethod
    def _months_ago(dt, months):
        """Return a datetime moved back by the given number of months."""
        year = dt.year
        month = dt.month - months
        while month < 1:
            month += 12
            year -= 1
        day = min(dt.day, calendar.monthrange(year, month)[1])
        return dt.replace(year=year, month=month, day=day)

    @staticmethod
    def _end_of_month(year, month):
        """Return a timezone-aware datetime for the last day of the given month."""
        last_day = calendar.monthrange(year, month)[1]
        return datetime.datetime(
            year, month, last_day, 23, 59, 59, tzinfo=datetime.timezone.utc
        )

    def get_default_start(self):
        """Return the default start date.

        Uses the earliest record's date field if data exists,
        otherwise falls back to 12 months ago.
        """
        now = timezone.now()
        earliest = (
            self.get_queryset()
            .order_by(self.date_field)
            .values_list(self.date_field, flat=True)
            .first()
        )
        if earliest:
            return earliest.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return self._months_ago(now, 11).replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )

    def parse_date_range(self, request):
        """Parse start/end query params (YYYY-MM), defaulting to earliest record through now."""
        now = timezone.now()
        default_end = now

        start_str = request.query_params.get("start")
        end_str = request.query_params.get("end")

        try:
            if start_str:
                year, month = map(int, start_str.split("-"))
                start = datetime.datetime(year, month, 1, tzinfo=datetime.timezone.utc)
            else:
                start = self.get_default_start()

            if end_str:
                year, month = map(int, end_str.split("-"))
                end = self._end_of_month(year, month)
            else:
                end = default_end
        except (ValueError, TypeError):
            start = self.get_default_start()
            end = default_end

        return start, end

    @staticmethod
    def _generate_months(start, end):
        """Yield (year, month) tuples for every month from start to end inclusive."""
        year, month = start.year, start.month
        while (year, month) <= (end.year, end.month):
            yield year, month
            month += 1
            if month > 12:
                month = 1
                year += 1

    def get(self, request):
        start, end = self.parse_date_range(request)
        qs = (
            self.get_queryset()
            .filter(**{f"{self.date_field}__range": (start, end)})
            .annotate(month=TruncMonth(self.date_field))
            .values("month")
            .annotate(**{self.annotation_name: Count("id")})
            .order_by("month")
        )

        # Index query results by (year, month) for quick lookup
        data_by_month = {}
        for entry in qs:
            key = (entry["month"].year, entry["month"].month)
            data_by_month[key] = entry[self.annotation_name]

        # Build complete series with zeros for missing months
        labels = []
        counts = []
        for year, month in self._generate_months(start, end):
            dt = datetime.date(year, month, 1)
            labels.append(dt.strftime("%b %Y"))
            counts.append(data_by_month.get((year, month), 0))

        return Response({"labels": labels, "counts": counts})


@extend_schema(
    summary="Get user growth data by month",
    description="Returns monthly user registration counts for charting. Admin only.",
    parameters=[
        OpenApiParameter(
            name="start",
            description="Start month (YYYY-MM). Defaults to 12 months ago.",
            required=False,
            type=str,
        ),
        OpenApiParameter(
            name="end",
            description="End month (YYYY-MM). Defaults to current month.",
            required=False,
            type=str,
        ),
    ],
    responses={
        200: {
            "type": "object",
            "properties": {
                "labels": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Month labels (e.g. 'Jan 2025')",
                },
                "counts": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "User count per month",
                },
            },
        },
    },
)
class AdminUserGrowthView(AdminTimeSeriesView):
    """Monthly user registration counts for the admin dashboard chart."""

    model = User
    date_field = "created_at"
