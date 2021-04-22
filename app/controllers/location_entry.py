import graphene
from datetime import datetime
from graphene.types.generic import GenericScalar

from app.controllers.utils import Void, atomic_transaction

from app.domain.permissions import (
    company_admin_at,
    can_actor_log_on_mission_at,
)
from app.helpers.authorization import with_authorization_policy, current_user
from app import db
from app.helpers.errors import (
    InvalidParamsError,
    MissionLocationAlreadySetError,
)
from app.helpers.graphene_types import graphene_enum_type
from app.models.company_known_address import (
    CompanyKnownAddressOutput,
    CompanyKnownAddress,
)
from app.models.address import Address, BaseAddressOutput
from app.models.location_entry import LocationEntryType, LocationEntry
from app.models import Mission


class CreateCompanyKnownAddress(graphene.Mutation):
    """
    Ajout d'un lieu enregistré.

    Renvoie le lieu nouvellement enregistré.
    """

    class Arguments:
        geo_api_data = graphene.Argument(
            GenericScalar,
            required=True,
            description="Informations sur le lieu au format GeoJSON",
        )
        alias = graphene.String(
            required=False, description="Nom usuel optionnel du lieu"
        )
        company_id = graphene.Int(
            required=True, description="Identifiant de l'entreprise",
        )

    Output = CompanyKnownAddressOutput

    @classmethod
    @with_authorization_policy(
        company_admin_at,
        get_target_from_args=lambda *args, **kwargs: kwargs["company_id"],
    )
    def mutate(cls, _, info, geo_api_data, company_id, alias=None):
        company_known_address = CompanyKnownAddress(
            alias=alias,
            address=Address.get_or_create(geo_api_data),
            company_id=company_id,
        )
        db.session.add(company_known_address)
        db.session.commit()
        return company_known_address


class EditCompanyKnownAddress(graphene.Mutation):
    """
    Edition du nom usuel d'un lieu enregistré.

    Renvoie le lieu modifié.
    """

    class Arguments:
        alias = graphene.String(
            required=False, description="Nouveau nom usuel"
        )
        company_known_address_id = graphene.Int(
            required=True, description="Identifiant du lieu à éditer"
        )

    Output = CompanyKnownAddressOutput

    @classmethod
    @with_authorization_policy(
        company_admin_at,
        get_target_from_args=lambda *args, **kwargs: CompanyKnownAddress.query.get(
            kwargs["company_known_address_id"]
        ).company_id,
    )
    def mutate(cls, _, info, alias, company_known_address_id):
        company_known_address = CompanyKnownAddress.query.get(
            company_known_address_id
        )
        company_known_address.alias = alias
        db.session.commit()
        return company_known_address


class TerminateCompanyKnownAddress(graphene.Mutation):
    """
    Retrait d'un véhicule de la liste.
    """

    class Arguments:
        company_known_address_id = graphene.Int(
            required=True, description="Identifiant du lieu à retirer"
        )

    Output = Void

    @classmethod
    @with_authorization_policy(
        company_admin_at,
        get_target_from_args=lambda *args, **kwargs: CompanyKnownAddress.query.get(
            kwargs["company_known_address_id"]
        ).company_id,
    )
    def mutate(cls, _, info, company_known_address_id):
        company_known_address = CompanyKnownAddress.query.get(
            company_known_address_id
        )
        company_known_address.dismiss(datetime.now())
        db.session.commit()
        return Void(success=True)


class LogMissionLocation(graphene.Mutation):
    class Arguments:
        geo_api_data = graphene.Argument(
            GenericScalar,
            required=False,
            description="Informations sur le lieu au format GeoJSON",
        )
        manual_address = graphene.Argument(
            graphene.String,
            required=False,
            description="Addresse donnée manuellement",
        )
        company_known_address_id = graphene.Int(
            required=False,
            description="Identifiant du lieu enregistré préalablement par l'entreprise",
        )
        mission_id = graphene.Int(
            required=True, description="Identifiant de la mission"
        )
        type = graphene.Argument(
            graphene_enum_type(LocationEntryType),
            required=True,
            description="Type d'enregistrement (début ou fin de mission)",
        )

    Output = BaseAddressOutput

    @classmethod
    @with_authorization_policy(
        can_actor_log_on_mission_at,
        get_target_from_args=lambda *args, **kwargs: Mission.query.get(
            kwargs["mission_id"]
        ),
    )
    def mutate(
        cls,
        _,
        info,
        mission_id,
        type,
        company_known_address_id=None,
        geo_api_data=None,
        manual_address=None,
    ):
        with atomic_transaction(commit_at_end=True):
            if (
                int(company_known_address_id is not None)
                + int(geo_api_data is not None)
                + int(manual_address is not None)
                != 1
            ):
                raise InvalidParamsError(
                    "Exactly one of companyKnownAddressId or geoApiData or manualAddress should be set"
                )

            mission = Mission.query.get(mission_id)

            company_known_address = None
            if company_known_address_id:
                company_known_address = CompanyKnownAddress.query.get(
                    company_known_address_id
                )
                if (
                    not company_known_address
                    or company_known_address.company_id != mission.company_id
                ):
                    raise InvalidParamsError("Invalid companyKnownAddressId")
                address = company_known_address.address
            elif geo_api_data:
                address = Address.get_or_create(geo_api_data)
            else:
                address = Address(manual=True, name=manual_address)
                db.session.add(address)

            existing_location_entry = [
                l for l in mission.location_entries if l.type == type
            ]
            existing_location_entry = (
                existing_location_entry[0] if existing_location_entry else None
            )

            if existing_location_entry:
                are_addresses_equal = (
                    address.name == existing_location_entry.address.name
                    if address.manual
                    and existing_location_entry.address.manual
                    else address == existing_location_entry.address
                )
                if are_addresses_equal:
                    return existing_location_entry.address
                raise MissionLocationAlreadySetError()

            location_entry = LocationEntry(
                _address=address,
                mission=mission,
                reception_time=datetime.now(),
                submitter=current_user,
                _company_known_address=company_known_address,
                type=type,
            )
            db.session.add(location_entry)

        return location_entry.address
