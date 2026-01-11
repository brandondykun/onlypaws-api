"""
Pagination classes for the feedback app.
"""
from rest_framework.pagination import PageNumberPagination


class FeedbackPagination(PageNumberPagination):
    page_size = 25

