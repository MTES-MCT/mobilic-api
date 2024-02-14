from time import time
from loguru import logger as lg

from sqlalchemy import event
from sqlalchemy.engine import Engine

lg.remove()
lg.add("sql_queries.log", format="{message}", level="INFO")


# Custom event listener for logging long queries
@event.listens_for(Engine, "before_cursor_execute")
def before_cursor_execute(
    conn, cursor, statement, parameters, context, executemany
):
    context._query_start_time = time()


@event.listens_for(Engine, "after_cursor_execute")
def after_cursor_execute(
    conn, cursor, statement, parameters, context, executemany
):
    total_time = time() - context._query_start_time
    lg.info(f"{total_time:.2f} seconds\n{statement}\n{parameters}\n")
