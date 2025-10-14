import requests
from typing import NamedTuple
from datetime import date

from app.helpers.errors import MobilicError
from app.helpers.insee_tranche_effectifs import format_tranche_effectif


def validate_siren(siren):
    """
    Validate SIREN format and return error message if invalid

    Args:
        siren: The SIREN string to validate

    Returns:
        str: Error message if invalid
    """
    if not siren:
        return "SIREN is required (received: empty value)"
    if len(siren) != 9:
        return f"SIREN must be exactly 9 characters (received: {len(siren)})"
    if not siren.isdigit():
        return "SIREN must contain only digits"
    return


class UnavailableSirenAPIError(MobilicError):
    code = "UNAVAILABLE_SIREN_API"


class InaccessibleSirenError(MobilicError):
    code = "INACCESSIBLE_SIREN"
    default_should_alert_team = False


class NoSirenAPICredentialsError(MobilicError):
    code = "NO_SIREN_API_CREDENTIALS"


SIREN_API_SIREN_INFO_ENDPOINT = "https://api.insee.fr/api-sirene/3.11/siret"
SIREN_API_PAGE_SIZE = 100


ADDRESS_STREET_TYPE_TO_LABEL = {
    "ALL": "Allée",
    "AV": "Avenue",
    "BD": "Boulevard",
    "CAR": "Carrefour",
    "CHE": "Chemin",
    "CHS": "Chaussée",
    "CITE": "Cité",
    "COR": "Corniche",
    "CRS": "Cours",
    "DOM": "Domaine",
    "DSC": "Descente",
    "ECA": "Ecart",
    "ESP": "Esplanade",
    "FG": "Faubourg",
    "GR": "Grande Rue",
    "HAM": "Hameau",
    "HLE": "Halle",
    "IMP": "Impasse",
    "LD": "Lieu dit",
    "LOT": "Lotissement",
    "MAR": "Marché",
    "MTE": "Montée",
    "PAS": "Passage",
    "PL": "Place",
    "PLN": "Plaine",
    "PLT": "Plateau",
    "PRO": "Promenade",
    "PRV": "Parvis",
    "QUA": "Quartier",
    "QUAI": "Quai",
    "RES": "Résidence",
    "RLE": "Ruelle",
    "ROC": "Rocade",
    "RPT": "Rond-point",
    "RTE": "Route",
    "RUE": "Rue",
    "SEN": "Sentier",
    "SQ": "Square",
    "TPL": "Terre-plein",
    "TRA": "Traverse",
    "VLA": "Villa",
    "VLGE": "Village",
    " ": "",
}

ADDRESS_NUMBER_REPETITION_TO_LABEL = {
    "B": "bis",
    "T": "ter",
    "Q": "quater",
    "C": "quinquies",
}


class LegalUnitInfo(NamedTuple):
    siren: str
    name: str
    tranche_effectif: str
    tranche_effectif_year: int
    activity: str
    activity_code: str
    creation_date: str


class FacilityInfo(NamedTuple):
    siret: str
    activity: str
    activity_code: str
    name: str
    address: str
    postal_code: str
    tranche_effectif: str
    tranche_effectif_year: int


def has_ceased_activity_from_siren_info(siren_info):
    return siren_info["uniteLegale"]["etatAdministratifUniteLegale"] == "C"


class SirenAPIClient:
    def __init__(self, api_key):
        self._api_key = api_key

    @property
    def api_key(self):
        if self._api_key:
            return self._api_key
        raise NoSirenAPICredentialsError(
            "No API key could be found for SIREN API"
        )

    def _request_siren_info(self, siren):
        # Documentation API SIRENE v3.11 :
        # - API Portal: https://api-apimanager.insee.fr/portal/environments/DEFAULT/apis/2ba0e549-5587-3ef1-9082-99cd865de66f/pages/6548510e-c3e1-3099-be96-6edf02870699/content
        # - Variables: https://www.sirene.fr/static-resources/documentation/v_sommaire_311.htm
        # - Features: https://www.sirene.fr/static-resources/documentation/sommaire_311.html
        siren_response = requests.get(
            f"{SIREN_API_SIREN_INFO_ENDPOINT}?q=siren:{siren}&nombre={SIREN_API_PAGE_SIZE}&date={date.today()}",
            headers={"X-INSEE-Api-Key-Integration": self.api_key},
            timeout=10,
        )
        if siren_response.status_code == 200:
            return siren_response
        if siren_response.status_code == 404:
            raise InaccessibleSirenError(
                f"SIREN {siren} was not found : {siren_response.json()}"
            )
        raise UnavailableSirenAPIError(
            f"Request to get info of SIREN {siren} failed : {siren_response.json()}"
        )

    @staticmethod
    def _format_address_number_repetition(address_repetition_number):
        if (
            not address_repetition_number
            or address_repetition_number
            not in ADDRESS_NUMBER_REPETITION_TO_LABEL
        ):
            return ""
        return (
            f" {ADDRESS_NUMBER_REPETITION_TO_LABEL[address_repetition_number]}"
        )

    @staticmethod
    def _format_address_street_type(address_street_type):
        if (
            not address_street_type
            or address_street_type not in ADDRESS_STREET_TYPE_TO_LABEL
        ):
            return ""
        return ADDRESS_STREET_TYPE_TO_LABEL[address_street_type]

    @staticmethod
    def _parse_address_to_simpler_format(address_info, is_secondary=False):
        secondary_flag = "2" if is_secondary else ""
        address = (
            f"{address_info[f'numeroVoie{secondary_flag}Etablissement'] or ''}{SirenAPIClient._format_address_number_repetition(address_info[f'indiceRepetition{secondary_flag}Etablissement'])}"
            f" {SirenAPIClient._format_address_street_type(address_info[f'typeVoie{secondary_flag}Etablissement'])} {address_info[f'libelleVoie{secondary_flag}Etablissement'] or ''}"
        )

        if address_info[f"codePostal{secondary_flag}Etablissement"]:
            postal_code = f"{address_info[f'codePostal{secondary_flag}Etablissement'] or ''} {address_info[f'libelleCommune{secondary_flag}Etablissement'] or ''}"
        else:
            postal_code = f"{address_info[f'libelleCommuneEtranger{secondary_flag}Etablissement'] or ''} {address_info[f'codePaysEtranger{secondary_flag}Etablissement'] or ''}"

        return {
            f"adresse{secondary_flag}": (
                address if len(address.replace(" ", "")) > 0 else None
            ),
            f"codePostal{secondary_flag}": (
                postal_code if len(postal_code.replace(" ", "")) > 0 else None
            ),
        }

    @staticmethod
    def _get_legal_unit_name(lu_dict):
        name = lu_dict["denominationUniteLegale"]
        if not name:
            if not lu_dict["nomUniteLegale"]:
                name = ""
            else:
                name = f"{lu_dict['prenom1UniteLegale']} {lu_dict['nomUsageUniteLegale'] or lu_dict['nomUniteLegale']}"
        return name

    @staticmethod
    def _raw_siren_info_with_clean_addresses(info):
        facilities = info["etablissements"]
        legal_unit_dict = {
            **facilities[0]["uniteLegale"],
            "siren": facilities[0]["siren"],
        }
        facilities_with_simplified_address = [
            dict(
                **{
                    k: v
                    for k, v in f.items()
                    if k
                    not in [
                        "siren",
                        "adresseEtablissement",
                        "adresse2Etablissement",
                        "uniteLegale",
                        "periodesEtablissement",
                    ]
                },
                **{
                    k: v
                    for k, v in f["periodesEtablissement"][0].items()
                    if not k.startswith("changement")
                },
                **SirenAPIClient._parse_address_to_simpler_format(
                    f["adresseEtablissement"], is_secondary=False
                ),
                **SirenAPIClient._parse_address_to_simpler_format(
                    f["adresse2Etablissement"], is_secondary=True
                ),
            )
            for f in facilities
        ]

        return dict(
            uniteLegale=legal_unit_dict,
            etablissements=facilities_with_simplified_address,
        )

    @staticmethod
    def _format_activity_from_naf_code(activity_code):
        from app.models import NafCode

        formatted_activity = activity_code
        activity = NafCode.get_code(activity_code) if activity_code else None
        if activity:
            formatted_activity = f"{activity.code} {activity.label}"
        return formatted_activity

    @staticmethod
    def parse_legal_unit_and_open_facilities_info_from_dict(clean_siren_info):
        # Spec of data retunred by API SIRENE v3.11 :
        # Variables: https://www.sirene.fr/static-resources/documentation/v_sommaire_311.htm
        legal_unit_dict = clean_siren_info["uniteLegale"]
        facilities_raw_info = clean_siren_info["etablissements"]

        legal_unit = LegalUnitInfo(
            siren=legal_unit_dict["siren"],
            name=SirenAPIClient._get_legal_unit_name(legal_unit_dict),
            tranche_effectif=format_tranche_effectif(
                legal_unit_dict["trancheEffectifsUniteLegale"]
            ),
            tranche_effectif_year=legal_unit_dict["anneeEffectifsUniteLegale"],
            activity_code=legal_unit_dict["activitePrincipaleUniteLegale"],
            activity=SirenAPIClient._format_activity_from_naf_code(
                legal_unit_dict["activitePrincipaleUniteLegale"]
            ),
            creation_date=(
                legal_unit_dict["dateCreationUniteLegale"]
                if legal_unit_dict["dateCreationUniteLegale"]
                else None
            ),
        )

        open_facilities = []
        for facility in facilities_raw_info:
            if facility["etatAdministratifEtablissement"] == "F":
                continue

            open_facilities.append(
                FacilityInfo(
                    siret=facility["siret"],
                    activity_code=facility["activitePrincipaleEtablissement"],
                    activity=SirenAPIClient._format_activity_from_naf_code(
                        facility["activitePrincipaleEtablissement"]
                    ),
                    name=facility["denominationUsuelleEtablissement"] or "",
                    address=facility["adresse"],
                    postal_code=facility["codePostal"],
                    tranche_effectif=format_tranche_effectif(
                        facility["trancheEffectifsEtablissement"]
                    ),
                    tranche_effectif_year=facility[
                        "anneeEffectifsEtablissement"
                    ],
                )
            )
        return legal_unit, open_facilities

    def get_siren_info(self, siren):
        siren_response = self._request_siren_info(siren)
        return self._raw_siren_info_with_clean_addresses(siren_response.json())

    def has_company_ceased_activity(self, siren):
        from app import app

        try:
            siren_info = self.get_siren_info(siren)
            return (
                has_ceased_activity_from_siren_info(siren_info)
            ), siren_info
        except InaccessibleSirenError:
            app.logger.error(f"Inaccessible siren {siren}")
            return False, None
