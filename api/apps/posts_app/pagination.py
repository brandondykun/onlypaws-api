from rest_framework.pagination import PageNumberPagination


class SearchedProfilesPagination(PageNumberPagination):
    page_size = 13


class ListExplorePostsPagination(PageNumberPagination):
    page_size = 24


class ListProfilePostsPagination(PageNumberPagination):
    page_size = 24


class ListSimilarPostsPagination(PageNumberPagination):
    page_size = 5


class FollowListPagination(PageNumberPagination):
    page_size = 15


class PostCommentsPagination(PageNumberPagination):
    page_size = 10


class CommentRepliesPagination(PageNumberPagination):
    page_size = 8
