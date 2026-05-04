from calendar import timegm
from datetime import datetime, timezone

import graphene
from flask import after_this_request, g
from sqlalchemy import or_

from app import app, db
from app.controllers.utils import Void
from app.domain.impersonation import (
    IMPERSONATION_EXPIRATION,
    create_admin_restore_token,
    create_impersonation_token,
    validate_impersonation_prerequisites,
)
from app.helpers.authentication import (
    AuthenticatedMutation,
    current_user,
)
from app.helpers.authorization import (
    admin_only,
    with_authorization_policy,
)
from app.helpers.errors import AuthorizationError
from app.models import Company, User
from app.models.employment import Employment


def _set_impersonation_access_cookie(
    response, token, user_id, expires_delta=None
):
    response.set_cookie(
        app.config["JWT_ACCESS_COOKIE_NAME"],
        value=token,
        httponly=True,
        secure=app.config["JWT_COOKIE_SECURE"],
        path=app.config["JWT_ACCESS_COOKIE_PATH"],
        samesite="Strict",
    )
    response.set_cookie(
        "userId",
        value=str(user_id),
        secure=app.config["JWT_COOKIE_SECURE"],
    )
    if expires_delta:
        expiry = datetime.now(timezone.utc) + expires_delta
        response.set_cookie(
            "atEat",
            value=str(timegm(expiry.utctimetuple())),
            secure=app.config["JWT_COOKIE_SECURE"],
        )


class StartImpersonationOutput(graphene.ObjectType):
    access_token = graphene.String(required=True)
    impersonated_user_id = graphene.Int(required=True)


class StartImpersonation(AuthenticatedMutation):
    class Arguments:
        user_id = graphene.Int(
            required=True,
            description="ID de l'utilisateur à impersonner",
        )

    Output = StartImpersonationOutput

    @classmethod
    @with_authorization_policy(admin_only)
    def mutate(cls, _, info, user_id):
        validate_impersonation_prerequisites(current_user)
        result = create_impersonation_token(current_user, user_id)

        @after_this_request
        def set_cookies(response):
            _set_impersonation_access_cookie(
                response,
                result["access_token"],
                result["impersonated_user_id"],
                expires_delta=IMPERSONATION_EXPIRATION,
            )
            return response

        return StartImpersonationOutput(**result)


class StopImpersonation(AuthenticatedMutation):
    class Arguments:
        pass

    Output = Void

    @classmethod
    def mutate(cls, _, info):
        impersonate_by = getattr(g, "impersonate_by", None)
        if not impersonate_by:
            raise AuthorizationError("Not in impersonation session")
        admin_user = User.query.get(impersonate_by)
        if not admin_user:
            raise AuthorizationError("Admin user not found")
        new_token = create_admin_restore_token(admin_user)

        @after_this_request
        def restore_cookies(response):
            _set_impersonation_access_cookie(
                response, new_token, admin_user.id
            )
            return response

        return Void(success=True)


class CompanySearchResult(graphene.ObjectType):
    name = graphene.String()
    siren = graphene.String()


class UserSearchResult(graphene.ObjectType):
    id = graphene.Int()
    email = graphene.String()
    first_name = graphene.String()
    last_name = graphene.String()
    companies = graphene.List(CompanySearchResult)


def _user_to_search_result(user):
    companies = []
    for emp in getattr(user, "employments", []):
        if emp.company:
            companies.append(
                CompanySearchResult(
                    name=emp.company.usual_name,
                    siren=emp.company.siren,
                )
            )
    seen = set()
    unique_companies = []
    for c in companies:
        key = (c.name, c.siren)
        if key not in seen:
            seen.add(key)
            unique_companies.append(c)
    return UserSearchResult(
        id=user.id,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        companies=unique_companies,
    )


PAGE_SIZE = 20


class UserSearchResultPage(graphene.ObjectType):
    results = graphene.List(UserSearchResult)
    has_more = graphene.Boolean()


class Query(graphene.ObjectType):
    search_users_for_impersonation = graphene.Field(
        UserSearchResultPage,
        search=graphene.String(required=True),
        offset=graphene.Int(default_value=0),
    )

    @with_authorization_policy(admin_only)
    def resolve_search_users_for_impersonation(self, info, search, offset=0):
        validate_impersonation_prerequisites(current_user)
        if len(search) < 3:
            return UserSearchResultPage(results=[], has_more=False)
        escaped = (
            search.replace("\\", "\\\\")
            .replace("%", "\\%")
            .replace("_", "\\_")
        )
        term = f"%{escaped}%"
        user_filters = or_(
            User.email.ilike(term, escape="\\"),
            User.first_name.ilike(term, escape="\\"),
            User.last_name.ilike(term, escape="\\"),
        )
        siren_escaped = f"{escaped}%"
        siren_subq = (
            db.session.query(Employment.user_id)
            .join(Company, Employment.company_id == Company.id)
            .filter(Company.siren.like(siren_escaped, escape="\\"))
            .subquery()
        )
        users = (
            User.query.options(
                db.joinedload(User.employments).joinedload(Employment.company)
            )
            .filter(or_(user_filters, User.id.in_(siren_subq)))
            .offset(offset)
            .limit(PAGE_SIZE + 1)
            .all()
        )
        has_more = len(users) > PAGE_SIZE
        return UserSearchResultPage(
            results=[_user_to_search_result(u) for u in users[:PAGE_SIZE]],
            has_more=has_more,
        )
