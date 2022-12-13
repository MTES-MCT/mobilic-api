import time
from secrets import token_hex
from authlib.oauth2.rfc6749 import ClientMixin, TokenMixin
from authlib.integrations.sqla_oauth2 import OAuth2AuthorizationCodeMixin

from app import db
from app.helpers.db import DateTimeStoredAsUTC
from app.models.base import BaseModel, RandomNineIntId


class OAuth2Client(BaseModel, RandomNineIntId, ClientMixin):
    __tablename__ = "oauth2_client"

    name = db.Column(db.String(255), nullable=False)
    secret = db.Column(db.String(120), nullable=False)
    redirect_uris = db.Column(db.ARRAY(db.String))
    whitelist_ips = db.Column(db.ARRAY(db.String))

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
        return redirect_uri in self.redirect_uris or "*" in self.redirect_uris

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

    @classmethod
    def create_client(cls, name, redirect_uris):
        return cls.create(
            name=name, redirect_uris=redirect_uris, secret=token_hex(60)
        )

    def __repr__(self):
        return "<OAuth2Client [{}] : {}, {}, {}>".format(
            self.id,
            self.name,
            self.secret,
            self.redirect_uris,
        )


class OAuth2Token(BaseModel, TokenMixin):
    __tablename__ = "oauth2_token"

    client_id = db.Column(
        db.Integer,
        db.ForeignKey("oauth2_client.id"),
        index=True,
        nullable=False,
    )
    token = db.Column(db.String(255), unique=True, nullable=False)
    user_id = db.Column(
        db.Integer, db.ForeignKey("user.id"), index=True, nullable=False
    )
    user = db.relationship("User", backref="oauth_tokens")

    revoked_at = db.Column(DateTimeStoredAsUTC)

    __table_args__ = (
        db.Constraint(name="only_one_active_token_per_user_and_client"),
    )

    def get_client_id(self):
        return self.client_id

    def get_scope(self):
        return ""

    def get_expires_in(self):
        return 86400

    def expires_at(self):
        return time.time() + 86400

    @property
    def revoked(self):
        return self.revoked_at is not None


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


class OAuth2ApiKey(BaseModel):
    __tablename__ = "oauth2_api_key"
    client_id = db.Column(
        db.Integer,
        db.ForeignKey("oauth2_client.id"),
        index=True,
        nullable=False,
    )
    client = db.relationship("OAuth2Client", backref="client")
    api_key = db.Column(db.String(255), nullable=False)
