import graphene
from flask import send_file
from io import BytesIO

from webargs import fields
from flask_apispec import use_kwargs, doc

from app import app
from app.helpers.tachograph import (
    generate_tachograph_parts,
    write_tachograph_archive,
    generate_tachograph_file_name,
)
from app.models import UserReadToken
from app.models.user_read_token import UserReadTokenOutput


class Query(graphene.ObjectType):
    user_read_token = graphene.Field(
        UserReadTokenOutput,
        token=graphene.String(required=True),
        description="Informations sur un jeton de lecture d'un historique utilisateur",
    )

    def resolve_user_read_token(self, info, token):
        return UserReadToken.get_token(token)
