from rest_framework.pagination import PageNumberPagination


class StandardPagination(PageNumberPagination):
    """
    Page-number pagination with a client-adjustable size.

    Deliberately not wired up as DEFAULT_PAGINATION_CLASS: every list view in
    this project is a plain APIView, and DRF only paginates automatically for
    GenericAPIView subclasses. Setting the default would look like it worked
    and silently do nothing. Views opt in via PaginatedListMixin instead.
    """

    page_size = 25
    page_size_query_param = 'page_size'
    max_page_size = 100


class PaginatedListMixin:
    """
    Pagination for hand-rolled APIViews.

    GenericAPIView gets this from its own plumbing; APIView has none, so this
    supplies just the paginator handling without dragging in the rest of the
    generic machinery.
    """

    pagination_class = StandardPagination

    @property
    def paginator(self):
        if not hasattr(self, '_paginator'):
            self._paginator = (
                self.pagination_class() if self.pagination_class else None)
        return self._paginator

    def paginated_response(self, queryset, serializer_class, request, **kwargs):
        """
        Serialize `queryset` one page at a time.

        Returns the standard {count, next, previous, results} envelope. Falls
        back to an unpaginated list only if pagination is switched off.
        """
        if self.paginator is None:
            serializer = serializer_class(queryset, many=True, **kwargs)
            from rest_framework.response import Response
            return Response(serializer.data)

        page = self.paginator.paginate_queryset(queryset, request, view=self)
        serializer = serializer_class(page, many=True, **kwargs)
        return self.paginator.get_paginated_response(serializer.data)
