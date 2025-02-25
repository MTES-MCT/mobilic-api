from app import db
from .base import AnonymizedModel


class AnonTeam(AnonymizedModel):
    __tablename__ = "anon_team"
    id = db.Column(db.Integer, primary_key=True)
    creation_time = db.Column(db.DateTime, nullable=False)
    company_id = db.Column(db.Integer, nullable=False)

    @classmethod
    def anonymize(cls, team):
        anonymized = cls()
        anonymized.id = cls.get_new_id("team", team.id)
        anonymized.company_id = cls.get_new_id("company", team.company_id)
        anonymized.creation_time = cls.truncate_to_month(team.creation_time)
        return anonymized


class AnonTeamAdminUser(AnonymizedModel):
    __tablename__ = "anon_team_admin_user"
    team_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, primary_key=True)

    @classmethod
    def anonymize(cls, relation):
        anonymized = cls()
        anonymized.team_id = cls.get_new_id("team", relation.team_id)
        anonymized.user_id = cls.get_new_id("user", relation.user_id)
        return anonymized


class AnonTeamKnownAddress(AnonymizedModel):
    __tablename__ = "anon_team_known_address"
    team_id = db.Column(db.Integer, primary_key=True)
    company_known_address_id = db.Column(db.Integer, primary_key=True)

    @classmethod
    def anonymize(cls, relation):
        anonymized = cls()
        anonymized.team_id = cls.get_new_id("team", relation.team_id)
        anonymized.company_known_address_id = cls.get_new_id(
            "company_known_address", relation.company_known_address_id
        )
        return anonymized
