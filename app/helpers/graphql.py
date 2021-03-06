from app import app

from flask_graphql import GraphQLView
from flask import request


def get_children_field_names(info):
    field_asts = info.field_asts[0].selection_set.selections
    return [field_ast.name.value for field_ast in field_asts]


class CustomGraphQLView(GraphQLView):
    def dispatch_request(self):
        try:
            request_data = self.parse_body()
        except:
            request_data = "Invalid body"
        response = super().dispatch_request()
        if request.method == "POST":
            # Do not log introspection queries
            is_introspection = False
            if type(request_data) is dict:
                if (
                    request_data.get("operationName", "")
                    == "IntrospectionQuery"
                ):
                    is_introspection = True
                elif "__schema" in request_data.get("query", ""):
                    is_introspection = True
            if not is_introspection:
                log_data = {
                    "status_code": response.status_code,
                    "graphql_request": request_data,
                }
                try:
                    log_data["response"] = response.json()
                except:
                    pass

                app.logger.info(
                    "Graphql op", extra=log_data,
                )
        return response
