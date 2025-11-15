"""
Pagination classes for the moderation app.
"""
from rest_framework.pagination import PageNumberPagination


class ReportPostsPagination(PageNumberPagination):
    page_size = 50

