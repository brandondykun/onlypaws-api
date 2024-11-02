from rest_framework.pagination import PageNumberPagination


class SearchedProfilesPagination(PageNumberPagination):
    page_size = 13


class ListExplorePostsPagination(PageNumberPagination):
    page_size = 24


class ListProfilePostsPagination(PageNumberPagination):
    page_size = 24


class ListSimilarPostsPagination(PageNumberPagination):
    page_size = 5
