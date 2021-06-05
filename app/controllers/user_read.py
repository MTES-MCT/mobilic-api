import graphene
from flask import g, send_file
from io import BytesIO

from webargs import fields
from flask_apispec import use_kwargs, doc

from app import app
from app.data_access.user import UserOutput
from app.helpers.tachograph import (
    generate_tachograph_parts,
    write_tachograph_archive,
    generate_tachograph_file_name,
)
from app.models import UserReadToken
from app.models.user_read_token import UserReadTokenOutput


class UserReadOutput(graphene.ObjectType):
    user = graphene.Field(UserOutput)
    token_info = graphene.Field(UserReadTokenOutput)


class Query(graphene.ObjectType):
    user_from_read_token = graphene.Field(
        UserReadOutput,
        token=graphene.String(required=True),
        description="Consultation des informations d'un utilisateur à partir d'un jeton de lecture",
    )

    def resolve_user_from_read_token(self, info, token):
        existing_token = UserReadToken.get_token(token)
        user = existing_token.user
        g.user = user
        info.context.max_activity_date = existing_token.creation_day
        info.context.min_activity_date = existing_token.history_start_day
        return UserReadOutput(user=user, token_info=existing_token)


@app.route("/users/generate_tachograph_file", methods=["POST"])
@doc(
    description="Génération de fichier C1B pour l'utilisateur et la période définis par le jeton d'accès"
)
@use_kwargs({"token": fields.Str(required=True)}, apply=True)
def generate_tachograph_file(token):
    existing_token = UserReadToken.get_token(token)
    tachograph_data = generate_tachograph_parts(
        existing_token.user,
        start_date=existing_token.history_start_day,
        end_date=existing_token.creation_day,
        only_activities_validated_by_admin=False,
        with_signatures=True,
        do_not_generate_if_empty=False,
    )
    file = BytesIO()
    file.write(write_tachograph_archive(tachograph_data))
    file.seek(0)

    return send_file(
        file,
        cache_timeout=0,
        mimetype="application/octet-stream",
        as_attachment=True,
        attachment_filename=generate_tachograph_file_name(existing_token.user),
    )
