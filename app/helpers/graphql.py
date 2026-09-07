import json
from functools import partial

from flask import request, g, Response
from flask_graphql import GraphQLView
from graphql import validate, execute, GraphQLError
from graphql.backend.core import GraphQLCoreBackend, GraphQLDocument
from graphql.execution import ExecutionResult
from graphql.language import ast as gql_ast
from graphql.language.ast import (
    Field,
    FragmentDefinition,
    FragmentSpread,
    InlineFragment,
)
from graphql.language.parser import parse
from graphql.language.printer import print_ast
from graphql.validation.rules import specified_rules
from graphql.validation.rules.overlapping_fields_can_be_merged import (
    OverlappingFieldsCanBeMerged,
)
from sentry_sdk import configure_scope

from app import app

GRAPHQL_MAX_BATCH_SIZE = 10

GRAPHQL_MAX_FIELDS = 2000
GRAPHQL_MAX_DEPTH = 15

# Above this threshold, skip the O(n²) OverlappingFieldsCanBeMerged
# rule during validation. Other rules (O(n)) still catch invalid
# queries normally.
_OVERLAP_CHECK_FIELD_THRESHOLD = 200

_SAFE_RULES = [
    r for r in specified_rules if r is not OverlappingFieldsCanBeMerged
]


def _count_fields(node):
    count = 1 if isinstance(node, Field) else 0
    if hasattr(node, "selection_set") and node.selection_set:
        for sel in node.selection_set.selections:
            count += _count_fields(sel)
    if hasattr(node, "definitions"):
        for defn in node.definitions:
            count += _count_fields(defn)
    return count


def _selection_set_depth(selection_set, fragments, seen):
    depth = 0
    for sel in selection_set.selections:
        if isinstance(sel, Field):
            child = (
                _selection_set_depth(sel.selection_set, fragments, seen)
                if sel.selection_set
                else 0
            )
            depth = max(depth, 1 + child)
        elif isinstance(sel, InlineFragment):
            depth = max(
                depth,
                _selection_set_depth(sel.selection_set, fragments, seen),
            )
        elif isinstance(sel, FragmentSpread):
            name = sel.name.value
            if name in seen or name not in fragments:
                continue
            depth = max(
                depth,
                _selection_set_depth(
                    fragments[name].selection_set, fragments, seen | {name}
                ),
            )
    return depth


def _query_depth(document_ast):
    fragments = {
        d.name.value: d
        for d in document_ast.definitions
        if isinstance(d, FragmentDefinition)
    }
    depth = 0
    for defn in document_ast.definitions:
        if not isinstance(defn, FragmentDefinition) and getattr(
            defn, "selection_set", None
        ):
            depth = max(
                depth,
                _selection_set_depth(defn.selection_set, fragments, set()),
            )
    return depth


def _safe_execute_and_validate(schema, document_ast, *args, **kwargs):
    do_validation = kwargs.pop("validate", True)
    if do_validation:
        field_count = _count_fields(document_ast)
        if field_count > GRAPHQL_MAX_FIELDS:
            return ExecutionResult(
                errors=[
                    GraphQLError(
                        "Query is too large: it contains more than"
                        f" {GRAPHQL_MAX_FIELDS} fields."
                    )
                ],
                invalid=True,
            )
        if _query_depth(document_ast) > GRAPHQL_MAX_DEPTH:
            return ExecutionResult(
                errors=[
                    GraphQLError(
                        "Query is too deep: it exceeds the maximum depth"
                        f" of {GRAPHQL_MAX_DEPTH}."
                    )
                ],
                invalid=True,
            )
        if field_count > _OVERLAP_CHECK_FIELD_THRESHOLD:
            rules = _SAFE_RULES
        else:
            rules = specified_rules
        errors = validate(schema, document_ast, rules=rules)
        if errors:
            return ExecutionResult(errors=errors, invalid=True)
    return execute(schema, document_ast, *args, **kwargs)


class SafeGraphQLBackend(GraphQLCoreBackend):
    """GraphQL backend that mitigates O(n²) validation DoS.

    For queries with more than _OVERLAP_CHECK_FIELD_THRESHOLD fields,
    the OverlappingFieldsCanBeMerged rule is skipped. All other
    validation rules still run normally.
    """

    def document_from_string(self, schema, document_string):
        if isinstance(document_string, gql_ast.Document):
            document_ast = document_string
            document_string = print_ast(document_ast)
        else:
            document_ast = parse(document_string)
        return GraphQLDocument(
            schema=schema,
            document_string=document_string,
            document_ast=document_ast,
            execute=partial(
                _safe_execute_and_validate,
                schema,
                document_ast,
                **self.execute_params,
            ),
        )


def _make_graphql_error_response(message, status_code=400):
    return Response(
        json.dumps({"errors": [{"message": message}]}),
        status=status_code,
        content_type="application/json",
    )


def _check_batch_limit(request_data):
    if isinstance(request_data, list):
        if len(request_data) > GRAPHQL_MAX_BATCH_SIZE:
            return _make_graphql_error_response(
                "Batch request contains too many operations."
                f" Maximum allowed is {GRAPHQL_MAX_BATCH_SIZE}."
            )
    return None


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
        operation_name = "default_operation_name"
        try:
            request_data = self.parse_body()
        except:
            request_data = "Invalid body"

        # Batch size protection
        if request.method == "POST" and isinstance(request_data, (dict, list)):
            rejection = _check_batch_limit(request_data)
            if rejection is not None:
                return rejection

        if request.method == "POST":
            # Do not log introspection queries
            try:
                is_introspection = False
                if type(request_data) is dict:
                    operation_name = request_data.get(
                        "operationName", operation_name
                    )
                    if operation_name == "IntrospectionQuery":
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
        with configure_scope() as scope:
            # source="custom" raises priority above FlaskIntegration's
            # "route" source -> the operation name actually sticks in Sentry.
            scope.set_transaction_name(operation_name, source="custom")
            response = super().dispatch_request()
            return response
