from app import app

from flask_graphql import GraphQLView
from flask import request


class CustomGraphQLView(GraphQLView):
    def dispatch_request(self):
        request_data = self.parse_body()
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
                app.logger.info(
                    "Graphql op",
                    extra={
                        "status_code": response.status_code,
                        "graphql_request": request_data,
                    },
                )
        return response
