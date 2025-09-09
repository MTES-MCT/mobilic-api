import json

import graphene
from graphene.types.generic import GenericScalar

from app import hashids
from app.models.company_certification import CertificationLevel
from app.domain.company import (
    get_current_certificate,
    get_start_last_certification_period,
    get_last_day_of_certification,
)


class CertificateCriterias(graphene.ObjectType):
    creation_time = graphene.DateTime(
        description="Date de calcul des critères."
    )
    attribution_date = graphene.Field(
        graphene.String,
        description="Date d'attribution du certificat au format AAAA-MM-JJ",
    )
    expiration_date = graphene.Field(
        graphene.String,
        description="Date d'expiration du certificat au format AAAA-MM-JJ",
    )
    compliancy = graphene.Int(
        description="Score du nombre de seuils règlementaires respectés."
    )
    admin_changes = graphene.Float(
        description="Pourcentage d'activités modifiées par le gestionnaire."
    )
    log_in_real_time = graphene.Float(
        description="Pourcentage d'activités renseignées en temps réel."
    )
    info = GenericScalar(
        required=False,
        description="Informations additionnelles sur le calcul.",
    )

    def resolve_info(
        self,
        info,
    ):
        return json.dumps(self.info)


class CompanyCertificationType(graphene.ObjectType):
    is_certified = graphene.Boolean(
        description="Indique si l'entreprise a la certification Mobilic"
    )
    certification_medal = graphene.Field(
        graphene.Enum.from_enum(CertificationLevel),
        description="Médaille de la certification en cours",
    )
    last_day_certified = graphene.Field(
        graphene.Date,
        description="Date la plus récente à laquelle l'entreprise cessera ou a cessé d'être certifiée.",
    )
    start_last_certification_period = graphene.Field(
        graphene.Date,
        description="Date de début de la dernière période de certification",
    )
    certificate_criterias = graphene.Field(
        CertificateCriterias,
        description="Critères de certificat du mois en cours",
    )
    badge_url = graphene.String(
        description="Url pour accéder au badge de certificat pour l'entreprise."
    )

    @classmethod
    def from_company_id(cls, company_id):
        current_certificate = get_current_certificate(company_id)
        start_last_certification_period = get_start_last_certification_period(
            company_id
        )
        last_day_certified = get_last_day_of_certification(company_id)
        badge_url = (
            f"/company-certification-badge/{hashids.encode(company_id)}"
        )
        if current_certificate:
            return cls(
                is_certified=current_certificate.certified,
                certification_medal=current_certificate.certification_level,
                last_day_certified=last_day_certified,
                start_last_certification_period=start_last_certification_period,
                certificate_criterias=CertificateCriterias(
                    **{
                        k: getattr(current_certificate, k)
                        for k in CertificateCriterias._meta.fields.keys()
                    }
                ),
                badge_url=badge_url,
            )
        else:
            return cls(
                is_certified=False,
                certification_medal=CertificationLevel.NO_CERTIFICATION,
                last_day_certified=last_day_certified,
                start_last_certification_period=start_last_certification_period,
                certificate_criterias=None,
                badge_url=badge_url,
            )
