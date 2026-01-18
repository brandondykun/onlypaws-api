"""
Pagination classes for the admin dashboard app.
"""

from rest_framework.pagination import PageNumberPagination


class AdminPagination(PageNumberPagination):
    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 100

