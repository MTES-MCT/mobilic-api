from base64 import b64encode, b64decode
from graphene import PageInfo
from datetime import datetime

from app.helpers.errors import InvalidParamsError


def _opacify_cursor_string(cs):
    return b64encode(cs.encode()).decode()


def parse_datetime_plus_id_cursor(cs):
    try:
        decoded_cursor = b64decode(cs).decode()
        time, id_ = decoded_cursor.split(",")
        time = datetime.fromisoformat(time)
        id_ = int(id_)
    except:
        raise InvalidParamsError("Invalid pagination cursor")
    return time, id_


def paginate_query(
    query,
    item_to_cursor,
    cursor_to_filter,
    orders,
    connection_cls=None,
    first=None,
    after=None,
    max_first=None,
):
    if after:
        try:
            decoded_after_cursor = b64decode(after).decode()
            query = query.filter(cursor_to_filter(decoded_after_cursor))
        except:
            raise InvalidParamsError("Invalid pagination cursor")
    query = query.order_by(*orders)

    actual_first = min(first or max_first, max_first) if max_first else first
    if actual_first:
        query = query.limit(actual_first + 1)

    results = query.all()
    has_next_page = False
    if actual_first and len(results) == actual_first + 1:
        results = results[:-1]
        has_next_page = True

    edges = [
        {"node": r, "cursor": _opacify_cursor_string(item_to_cursor(r))}
        for r in results
    ]
    page_info = PageInfo(
        has_next_page=has_next_page,
        has_previous_page=False,
        start_cursor=_opacify_cursor_string(item_to_cursor(results[0]))
        if results
        else None,
        end_cursor=_opacify_cursor_string(item_to_cursor(results[-1]))
        if results
        else None,
    )

    if connection_cls:
        return connection_cls(
            edges=[connection_cls.Edge(**edge) for edge in edges],
            page_info=page_info,
        )

    return edges, page_info


def to_connection(
    iterable, connection_cls, has_next_page, get_cursor, first=None
):
    if first and len(iterable) > first:
        iterable = iterable[:first]
        has_next_page = True

    edges = [
        connection_cls.Edge(
            node=item, cursor=_opacify_cursor_string(get_cursor(item))
        )
        for item in iterable
    ]
    return connection_cls(
        edges=edges,
        page_info=PageInfo(
            has_previous_page=False,
            has_next_page=has_next_page,
            start_cursor=edges[0].cursor if edges else None,
            end_cursor=edges[-1].cursor if edges else None,
        ),
    )
