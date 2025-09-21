from rest_framework.pagination import PageNumberPagination


class NotificationsPagination(PageNumberPagination):
    page_size = 25
