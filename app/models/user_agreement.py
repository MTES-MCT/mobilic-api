import datetime
from enum import Enum

from sqlalchemy.orm import backref
from app import db, app
from app.models import User
from app.models.base import BaseModel
from app.models.utils import enum_column

from app.controllers.utils import atomic_transaction


class UserAgreementStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    __description__ = """
    - "pending" : l'utilisateur n'a pas encore accepté ou refusé les cgus.
    - "accepted" : l'utilisateur a accepté les cgus
    - "rejected" : l'utilisateur a refusé les cgus
    """


CGU_DELETE_ACCOUNT_DELAY_IN_DAYS = 10


class UserAgreement(BaseModel):
    backref_base_name = "user_agreements"

    user_id = db.Column(
        db.Integer, db.ForeignKey("user.id"), nullable=False, index=True
    )
    user = db.relationship(
        "User", backref=backref("user_agreements", lazy=True)
    )
    cgu_version = db.Column(db.String(5), nullable=False, index=True)
    answer_date = db.Column(
        db.DateTime, nullable=False, server_default=db.func.now()
    )
    status = enum_column(UserAgreementStatus, nullable=False)
    expires_at = db.Column(db.DateTime)
    transferred_data_date = db.Column(db.DateTime)
    is_blacklisted = db.Column(db.Boolean)

    __table_args__ = (
        db.UniqueConstraint("user_id", "cgu_version", name="unique_user_cgu"),
    )

    @staticmethod
    def get_or_create(user_id, cgu_version="", initial_status=None):
        if cgu_version == "":
            cgu_version = app.config["CGU_VERSION"]

        existing_user_agreement = UserAgreement.query.filter(
            UserAgreement.user_id == user_id,
            UserAgreement.cgu_version == cgu_version,
        ).one_or_none()
        if existing_user_agreement:
            return existing_user_agreement

        new_user_agreement = UserAgreement(
            user_id=user_id,
            cgu_version=cgu_version,
            status=initial_status
            if initial_status
            else UserAgreementStatus.PENDING,
            creation_time=datetime.datetime.now(),
            is_blacklisted=False,
        )
        db.session.add(new_user_agreement)
        db.session.commit()

        return new_user_agreement

    @staticmethod
    def get(user_id, cgu_version):
        return UserAgreement.query.filter(
            UserAgreement.user_id == user_id,
            UserAgreement.cgu_version == cgu_version,
        ).one_or_none()

    @staticmethod
    def is_user_blacklisted(user_id):
        cgu_version = app.config["CGU_VERSION"]
        existing_user_agreement = UserAgreement.get(
            user_id=user_id, cgu_version=cgu_version
        )
        if existing_user_agreement is None:
            return False

        if existing_user_agreement.is_blacklisted:
            return True

        if existing_user_agreement.status != UserAgreementStatus.REJECTED:
            return False

        if not existing_user_agreement.expires_at:
            return False

        if existing_user_agreement.expires_at < datetime.datetime.now():
            UserAgreement.blacklist_user(user_id=user_id)
            return True

        return False

    @staticmethod
    def has_user_rejected(user_id):
        cgu_version = app.config["CGU_VERSION"]
        existing_user_agreement = UserAgreement.get(
            user_id=user_id, cgu_version=cgu_version
        )
        if existing_user_agreement is None:
            return False
        return existing_user_agreement.status == UserAgreementStatus.REJECTED

    @staticmethod
    def blacklist_user(user_id):
        cgu_version = app.config["CGU_VERSION"]
        existing_user_agreement = UserAgreement.get(
            user_id=user_id, cgu_version=cgu_version
        )
        if existing_user_agreement is None:
            return

        with atomic_transaction(commit_at_end=True):
            today = datetime.date.today()
            existing_user_agreement.is_blacklisted = True

            user = User.query.get(user_id)
            employments = user.active_employments_at(today)
            for employment in employments:
                employment.end_date = today - datetime.timedelta(days=1)

    @staticmethod
    def set_transferred_data_date(user_id):
        cgu_version = app.config["CGU_VERSION"]
        existing_user_agreement = UserAgreement.get(
            user_id=user_id, cgu_version=cgu_version
        )
        if existing_user_agreement is None:
            return

        with atomic_transaction(commit_at_end=True):
            existing_user_agreement.transferred_data_date = (
                datetime.datetime.now()
            )

    def reject(self):
        self.status = UserAgreementStatus.REJECTED
        self.is_blacklisted = False
        self.expires_at = datetime.datetime.combine(
            datetime.datetime.today()
            + datetime.timedelta(days=CGU_DELETE_ACCOUNT_DELAY_IN_DAYS),
            datetime.time.min,
        )
        self.answer_date = datetime.datetime.now()

    def accept(self):
        self.status = UserAgreementStatus.ACCEPTED
        self.is_blacklisted = False
        self.expires_at = None
        self.answer_date = datetime.datetime.now()
