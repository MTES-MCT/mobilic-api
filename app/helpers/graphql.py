from app import app

from flask_graphql import GraphQLView
from flask import request, g


def parse_graphql_request_info(request_data):
    if type(request_data) is not list or len(request_data) == 1:
        actual_request_data = (
            request_data[0] if type(request_data) is list else request_data
        )
        return dict(
            vars=actual_request_data.get("variables", {}),
            graphql_op=actual_request_data.get("operationName", None),
            graphql_op_short=actual_request_data.get("operationName", None),
        )
    return dict(
        vars=[r.get("variables", {}) for r in request_data],
        graphql_op=[r.get("operationName", None) for r in request_data],
        graphql_op_short=f'{request_data[0].get("operationName", None)} + {len(request_data) - 1}',
    )


class CustomGraphQLView(GraphQLView):
    """
    Add request information to log context. For each request we want :
    - the graphql query text
    - graphql variables if they exist
    - operation name
    """

    def dispatch_request(self):
        try:
            request_data = self.parse_body()
        except:
            request_data = "Invalid body"
        if request.method == "POST":
            # Do not log introspection queries
            try:
                is_introspection = False
                if type(request_data) is dict:
                    if (
                        request_data.get("operationName", "")
                        == "IntrospectionQuery"
                    ):
                        is_introspection = True
                    else:
                        query = request_data.get("query", "")
                        if hasattr(query, "__iter__") and "__schema" in query:
                            is_introspection = True
                if not is_introspection:
                    g.log_info["is_graphql"] = True
                    g.log_info["json"] = request_data
                    g.log_info.update(parse_graphql_request_info(request_data))
                else:
                    g.log_info["no_log"] = True
            except Exception as e:
                app.logger.warning(
                    f"Could not add GraphQl request info to log context because of following error {e}"
                )
        response = super().dispatch_request()
        return response
