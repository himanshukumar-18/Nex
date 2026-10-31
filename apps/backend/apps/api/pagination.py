"""
NEX Backend — API pagination classes.

Two pagination strategies are provided:

  NexPageNumberPagination
    Simple offset-based pagination suitable for browsable collections where
    the caller specifies a page number.  Best for small to medium result sets
    where jumping to an arbitrary page is a user requirement.

    Query parameters:
      page      — 1-based page number (default 1)
      page_size — items per page (default 20, max 100)

    Response envelope:
      {
        "count":    <total_item_count>,
        "next":     <url_or_null>,
        "previous": <url_or_null>,
        "results":  [...]
      }

  NexCursorPagination
    Stable cursor-based pagination suitable for large or frequently-updated
    collections (agent runs, audit logs, events).  Prevents the "page drift"
    problem that affects offset pagination when items are inserted or deleted
    between page requests.

    Query parameters:
      cursor    — opaque server-issued cursor token
      page_size — items per page (default 20, max 100)

    Response envelope:
      {
        "next":     <url_or_null>,
        "previous": <url_or_null>,
        "results":  [...]
      }

Selection guidance:
  - Use NexPageNumberPagination for resource lists where random access matters
    (projects, repositories, team members).
  - Use NexCursorPagination for high-volume, append-heavy collections (agent
    runs, audit logs) where total count is expensive and page stability matters.
"""

from rest_framework.pagination import CursorPagination, PageNumberPagination


class NexPageNumberPagination(PageNumberPagination):
    """
    Offset-based page-number pagination for NEX REST API collections.

    Produces a stable response envelope across all paginated endpoints.
    """

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100
    page_query_param = "page"


class NexCursorPagination(CursorPagination):
    """
    Cursor-based pagination for high-volume or frequently-updated collections.

    Cursor values are opaque to the client.
    Ordering enforces a deterministic tie-breaker: `("-created_at", "-id")`.
    This guarantees stable cursor pagination in PostgreSQL even when two
    rows share identical millisecond timestamps.
    """

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100
    ordering = ("-created_at", "-id")

