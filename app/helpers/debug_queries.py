from app import app
from flask_sqlalchemy import get_debug_queries
from colorama import Fore, Style
import sqlparse
import re

postgreSQL_keywords = {
    "SELECT",
    "FROM",
    "WHERE",
    "AS",
    "CASE",
    "AND",
    "OR",
    "ORDER",
    "LEFT",
    "RIGHT",
    "INNER",
    "OUTER",
    "JOIN",
    "ON",
    "GROUP",
    "HAVING",
    "BY",
    "ASC",
    "DESC",
    "LIMIT",
    "OFFSET",
    "INSERT",
    "INTO",
    "VALUES",
    "UPDATE",
    "SET",
    "DELETE",
    "USING",
    "DISTINCT ON",
    "DISTINCT",
    "WITH",
    "WHEN",
    "ELSE",
    "THEN",
    "END",
    "IN",
}

operators = {
    "IS NULL",
    "IS NOT NULL",
    "=",
    "!=",
    ">",
    "<",
    ">=",
    "<=",
    "LIKE",
    "BETWEEN",
}

data_types = {
    "INT",
    "INTEGER",
    "SMALLINT",
    "BIGINT",
    "DECIMAL",
    "NUMERIC",
    "REAL",
    "DOUBLE PRECISION",
    "SERIAL",
    "BIGSERIAL",
    "DATE",
    "TIME",
    "TIMESTAMP",
    "TEXT",
    "CHAR",
    "CHARACTER",
    "VARCHAR",
    "CHARACTER VARYING",
    "BOOLEAN",
    "BIT",
    "VARBIT",
    "UUID",
    "JSON",
    "JSONB",
    "XML",
    "HSTORE",
    "ARRAY",
    "COMPOSITE",
    "ENUM",
}


@app.after_request
def sql_debug(response):
    queries = list(get_debug_queries())
    total_duration = 0.0
    regex = r"(?<!\w)({})(?!\w)"
    for q in queries:
        total_duration += q.duration
        stmt = str(q.statement % q.parameters)

        def colorize_sql_query(sql_query):
            formatted_query = sqlparse.format(
                sql_query, reindent_aligned=True, keyword_case="upper"
            )
            colored_query = formatted_query

            for keyword in postgreSQL_keywords:
                colored_query = re.sub(
                    regex.format(re.escape(keyword)),
                    f"{Fore.CYAN}{keyword}{Style.RESET_ALL}",
                    colored_query,
                )

            for operator in operators:
                colored_query = re.sub(
                    regex.format(re.escape(operator)),
                    f"{Fore.YELLOW}{operator}{Style.RESET_ALL}",
                    colored_query,
                )

            for data_type in data_types:
                colored_query = re.sub(
                    regex.format(re.escape(data_type)),
                    f"{Fore.GREEN}{data_type}{Style.RESET_ALL}",
                    colored_query,
                )

            colored_query = re.sub(
                r"(?<=\.)\w+",
                lambda x: f"{Fore.MAGENTA}{Style.BRIGHT}{x.group()}{Style.RESET_ALL}",
                colored_query,
            )

            return colored_query

        colored_query = colorize_sql_query(stmt)

        print(f"{Fore.YELLOW}Query:{Style.RESET_ALL}\n{colored_query}")
        print(
            f"{Fore.YELLOW}Duration:{Style.RESET_ALL} {Fore.GREEN}{round(q.duration * 1000, 2)}ms{Style.RESET_ALL}\n"
        )

    print("=" * 80 + "\n")

    print("=" * 80)
    print(
        f"{Style.BRIGHT}SQL Queries - {Style.RESET_ALL}{len(queries)}{Style.BRIGHT} Queries Executed in {Style.RESET_ALL}{round(total_duration * 1000, 2)}ms"
    )
    print("=" * 80)

    return response
