from authlib.oauth2.rfc6749 import ClientMixin
from authlib.integrations.sqla_oauth2 import OAuth2AuthorizationCodeMixin

from app import db
from app.models.base import BaseModel


class OAuth2Client(BaseModel, ClientMixin):
    __tablename__ = "oauth2_client"

    name = db.Column(db.String(255), nullable=False)
    secret = db.Column(db.String(120), nullable=False)
    redirect_uris = db.Column(db.ARRAY(db.String))

    def get_client_id(self):
        return self.id

    def get_default_redirect_uri(self):
        redirect_uris = self.redirect_uris
        if redirect_uris:
            return redirect_uris[0]
        return None

    def get_allowed_scope(self, scope):
        return ""

    def check_redirect_uri(self, redirect_uri):
        return redirect_uri in self.redirect_uris

    def has_client_secret(self):
        return bool(self.secret)

    def check_client_secret(self, client_secret):
        return self.secret == client_secret

    def check_token_endpoint_auth_method(self, method):
        return True

    def check_response_type(self, response_type):
        return True

    def check_grant_type(self, grant_type):
        return grant_type == "authorization_code"


class OAuth2AuthorizationCode(BaseModel, OAuth2AuthorizationCodeMixin):
    __tablename__ = "oauth2_authorization_code"

    user_id = db.Column(
        db.Integer, db.ForeignKey("user.id"), index=True, nullable=False
    )
    user = db.relationship("User", backref="authorization_codes")

    client_id = db.Column(
        db.Integer,
        db.ForeignKey("oauth2_client.id"),
        index=True,
        nullable=False,
    )
    client = db.relationship("OAuth2Client", backref="authorization_codes")
