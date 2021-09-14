import requests
from typing import NamedTuple
from datetime import date

from app.helpers.errors import MobilicError


class UnavailableSirenAPIError(MobilicError):
    code = "UNAVAILABLE_SIREN_API"


class InaccessibleSirenError(MobilicError):
    code = "INACCESSIBLE_SIREN"
    default_should_alert_team = False


class NoSirenAPICredentialsError(MobilicError):
    code = "NO_SIREN_API_CREDENTIALS"


SIREN_API_TOKEN_ENDPOINT = "https://api.insee.fr/token"
SIREN_API_SIREN_INFO_ENDPOINT = (
    "https://api.insee.fr/entreprises/sirene/V3/siret/"
)


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


class FacilityInfo(NamedTuple):
    siret: str
    siren: str
    activity: str
    company_name: str
    name: str
    address: str
    postal_code: str


class SirenAPIClient:
    def __init__(self, api_key):
        self._api_key = api_key
        self.access_token = None

    @property
    def api_key(self):
        if self._api_key:
            return self._api_key
        raise NoSirenAPICredentialsError(
            "No API key could be found for SIREN API"
        )

    def _generate_access_token(self):
        # From https://api.insee.fr/catalogue/site/themes/wso2/subthemes/insee/pages/application.jag?name=DefaultApplication&#subscription
        token_response = requests.post(
            SIREN_API_TOKEN_ENDPOINT,
            data={"grant_type": "client_credentials"},
            headers={"Authorization": f"Basic {self.api_key}"},
            timeout=5,
        )
        if not token_response.status_code == 200:
            raise UnavailableSirenAPIError(
                f"Request to generate access tokens for SIREN API failed : {token_response.json()}"
            )
        token_response_json = token_response.json()
        self.access_token = token_response_json["access_token"]

    def _request_siren_info(self, siren, retry_if_bad_token=True):
        # From :
        # - https://api.insee.fr/catalogue/site/themes/wso2/subthemes/insee/pages/item-info.jag?name=Sirene&version=V3&provider=insee
        # - https://api.insee.fr/catalogue/site/themes/wso2/subthemes/insee/templates/api/documentation/download.jag?tenant=carbon.super&resourceUrl=/registry/resource/_system/governance/apimgt/applicationdata/provider/insee/Sirene/V3/documentation/files/INSEE%20Documentation%20API%20Sirene%20Services-V3.9.pdf
        if not self.access_token:
            self._generate_access_token()
        siren_response = requests.get(
            f"{SIREN_API_SIREN_INFO_ENDPOINT}?q=siren:{siren}&date={date.today()}",
            headers={"Authorization": f"Bearer {self.access_token}"},
            timeout=10,
        )
        if siren_response.status_code == 401 and retry_if_bad_token:
            self._generate_access_token()
            return self._request_siren_info(siren, retry_if_bad_token=False)
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
            f"adresse{secondary_flag}": address
            if len(address.replace(" ", "")) > 0
            else None,
            f"codePostal{secondary_flag}": postal_code
            if len(postal_code.replace(" ", "")) > 0
            else None,
        }

    @staticmethod
    def _parse_siren_info(info):
        facilities = info["etablissements"]
        company = {
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
            uniteLegale=company,
            etablissements=facilities_with_simplified_address,
        )

    @staticmethod
    def extract_current_facilities_short_info(parsed_siren_info):
        from app.models import NafCode

        # Spec of the data returned by the SIREN API : https://api.insee.fr/catalogue/site/themes/wso2/subthemes/insee/templates/api/documentation/download.jag?tenant=carbon.super&resourceUrl=/registry/resource/_system/governance/apimgt/applicationdata/provider/insee/Sirene/V3/documentation/files/INSEE%20Documentation%20API%20Sirene%20Variables-V3.9.pdf
        open_facilities = []
        for facility in parsed_siren_info["etablissements"]:
            if facility["etatAdministratifEtablissement"] == "F":
                continue

            company = parsed_siren_info["uniteLegale"]
            company_name = company["denominationUniteLegale"]
            if not company_name:
                if not company["nomUniteLegale"]:
                    company_name = ""
                else:
                    company_name = f"{company['prenom1UniteLegale']} {company['nomUsageUniteLegale'] or company['nomUniteLegale']}"

            activity_code = facility["activitePrincipaleEtablissement"]
            activity = (
                NafCode.get_code(activity_code) if activity_code else None
            )
            if activity:
                activity_code = f"{activity.code} {activity.label}"

            open_facilities.append(
                FacilityInfo(
                    siren=company["siren"],
                    siret=facility["siret"],
                    company_name=company_name,
                    activity=activity_code,
                    name=facility["denominationUsuelleEtablissement"] or "",
                    address=facility["adresse"],
                    postal_code=facility["codePostal"],
                )._asdict()
            )
        return open_facilities

    def get_siren_info(self, siren):
        siren_response = self._request_siren_info(siren)
        return self._parse_siren_info(siren_response.json())
