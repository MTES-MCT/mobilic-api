import requests
from typing import NamedTuple

from app.helpers.errors import (
    UnavailableSirenAPIError,
    InaccessibleSirenError,
    NoSirenAPICredentialsError,
)

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
            f"{SIREN_API_SIREN_INFO_ENDPOINT}?q=siren:{siren}",
            headers={"Authorization": f"Bearer {self.access_token}"},
        )
        if siren_response.status_code == 401 and retry_if_bad_token:
            self._generate_access_token()
            return self._request_siren_info(siren, retry_if_bad_token=False)
        if siren_response.status_code == 200:
            print(siren_response.json())
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
    def _parse_siren_info(info):
        # From https://api.insee.fr/catalogue/site/themes/wso2/subthemes/insee/templates/api/documentation/download.jag?tenant=carbon.super&resourceUrl=/registry/resource/_system/governance/apimgt/applicationdata/provider/insee/Sirene/V3/documentation/files/INSEE%20Documentation%20API%20Sirene%20Variables-V3.9.pdf
        facilities = []
        for facility in info["etablissements"]:
            periods = facility["periodesEtablissement"]
            latest_period = [p for p in periods if not p["dateFin"]]
            latest_period = latest_period[0] if latest_period else None
            if (
                not latest_period
                or latest_period["etatAdministratifEtablissement"] == "F"
            ):
                continue

            address_info = facility["adresseEtablissement"]
            address = (
                f"{address_info['numeroVoieEtablissement'] or ''}{SirenAPIClient._format_address_number_repetition(address_info['indiceRepetitionEtablissement'])}"
                f" {SirenAPIClient._format_address_street_type(address_info['typeVoieEtablissement'])} {address_info['libelleVoieEtablissement']}"
            )

            if address_info["codePostalEtablissement"]:
                postal_code = f"{address_info['codePostalEtablissement']} {address_info['libelleCommuneEtablissement']}"
            else:
                postal_code = f"{address_info['libelleCommuneEtrangerEtablissement']} {address_info['codePaysEtrangerEtablissement']}"

            company = facility["uniteLegale"]
            company_name = company["denominationUniteLegale"]
            if not company_name:
                if not company["nomUniteLegale"]:
                    company_name = ""
                else:
                    company_name = f"{company['prenom1UniteLegale']} {company['nomUsageUniteLegale'] or company['nomUniteLegale']}"

            facilities.append(
                FacilityInfo(
                    siren=facility["siren"],
                    siret=facility["siret"],
                    company_name=company_name,
                    name=latest_period["denominationUsuelleEtablissement"]
                    or "",
                    address=address,
                    postal_code=postal_code,
                )._asdict()
            )
        return facilities

    # TODO : cache this using Redis
    def get_siren_info(self, siren):
        siren_response = self._request_siren_info(siren)
        return self._parse_siren_info(siren_response.json())
