"""
Pagination classes for the interactions app.
"""

from rest_framework.pagination import PageNumberPagination


class FollowListPagination(PageNumberPagination):
    page_size = 15


class PostCommentsPagination(PageNumberPagination):
    page_size = 10


class CommentRepliesPagination(PageNumberPagination):
    page_size = 8

