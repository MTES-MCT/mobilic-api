import tempfile
import xml.etree.cElementTree as ET
from dataclasses import dataclass
from datetime import datetime

from flask import send_file

from app.models import ControlLocation, ControllerUser

TRANSPORT_TYPES = {
    "unknown": -1,
    "interieur": 0,
    "international": 1,
    "cabotage": 2,
}


@dataclass
class GrecoInfraction:
    natinf: str
    id: str
    short_id: str
    label: str


def add_content_element(element, field_name, content):
    sub_element = ET.SubElement(ET.SubElement(element, field_name), "content")
    if content != "":
        sub_element.text = content


def add_date_element(element, field_name, dt):
    date_element = ET.SubElement(ET.SubElement(element, field_name), "content")
    ET.SubElement(date_element, "Year").text = str(dt.year)
    ET.SubElement(date_element, "Month").text = str(dt.month)
    ET.SubElement(date_element, "Day").text = str(dt.day)

    if isinstance(dt, datetime):
        ET.SubElement(date_element, "Hour").text = str(dt.hour)
        ET.SubElement(date_element, "Min").text = str(dt.minute)
    else:
        ET.SubElement(date_element, "Hour").text = str(0)
        ET.SubElement(date_element, "Min").text = str(0)


def process_control(control, bdc, doc, infractions):
    control_location = ControlLocation.query.filter(
        ControlLocation.id == bdc.get("location_id")
    ).first()
    controller = ControllerUser.query.filter(
        ControllerUser.id == control.controller_id
    ).first()
    element_control = ET.SubElement(doc, "Controle")

    add_date_element(element_control, "controleDate", control.creation_time)

    add_content_element(
        element_control,
        "lieuDepartement_Intitule",
        bdc.get("location_department", ""),
    )

    departement_code = str(control_location.department).zfill(2)
    add_content_element(
        element_control,
        "lieuDepartement_Code",
        departement_code,
    )

    add_content_element(element_control, "lieuVoie", "")
    add_content_element(
        element_control, "lieuDescription", control_location.label
    )

    add_content_element(element_control, "controleur_Civilite", "-")
    add_content_element(
        element_control, "controleur_Nom", controller.last_name
    )
    add_content_element(
        element_control, "controleur_Prenom", controller.first_name
    )
    add_content_element(
        element_control, "controleur_Identification", controller.greco_id
    )

    add_content_element(
        element_control, "lieuAire_Code", str(control_location.postal_code)
    )
    # ?
    add_content_element(
        element_control, "lieuType", str(control_location.greco_extra1)
    )
    add_content_element(element_control, "lieuTypeVoie", "")
    add_content_element(
        element_control, "lieuAire_Intitule", control_location.greco_label
    )
    add_content_element(
        element_control, "lieuAire_TypeLieu", control_location.type
    )

    add_content_element(
        element_control, "lieuCommune_Intitule", bdc.get("location_commune")
    )
    add_content_element(
        element_control,
        "lieuCommune_CodePostal",
        str(control_location.postal_code),
    )

    add_content_element(
        element_control, "immatriculation", control.vehicle_registration_number
    )

    add_date_element(
        element_control, "debutPeriodeControle", control.history_start_date
    )

    # Boolean 0 ou 1
    # ?
    add_content_element(element_control, "transportExceptionnel", str(0))

    add_content_element(
        element_control,
        "transportType",
        str(TRANSPORT_TYPES[bdc.get("transport_type", "unknown")]),
    )

    # Boolean 0 ou 1
    # ?
    add_content_element(element_control, "pesee", str(0))

    # Controle Technique de - de 3 mois
    # Boolean 0 ou 1
    # ?
    add_content_element(element_control, "cT3Mois", str(0))

    add_content_element(
        element_control,
        "observationBulletinControle",
        bdc.get("observation", ""),
    )
    add_content_element(element_control, "numeroBDC", control.reference)

    # TODO
    # Type de chronotachygraphe
    # 0 Analogique
    # 1 Numérique
    # 2 Sans
    # 3 Les deux
    # ?
    add_content_element(element_control, "typeTachygraphe", str(1))

    add_date_element(
        element_control, "finPeriodeControle", control.history_end_date
    )

    add_content_element(
        element_control, "nbjouractivites", str(control.nb_controlled_days)
    )

    # Boolean 0 ou 1
    # ?
    add_content_element(
        element_control, "default_Vehicule_MarchandiseDangereuse", str(0)
    )

    if len(infractions) > 0:
        infractions_element = ET.SubElement(
            ET.SubElement(
                ET.SubElement(element_control, "rRecapInfraction"), "content"
            ),
            "idlist",
        )
        for r in infractions:
            ET.SubElement(
                ET.SubElement(infractions_element, "id"), "DbValue"
            ).text = r.id

    controller_name = f"{controller.first_name} {controller.last_name}"
    initials = "".join(
        [part[0].capitalize() for part in controller_name.split()]
    )
    return f"R{departement_code}{initials}{control.creation_time.strftime('%Y%m%d%H%M')}{control.vehicle_registration_number}.xml"


def process_company(control, bdc, doc):
    element_company = ET.SubElement(doc, "Entreprise")
    add_content_element(element_company, "raisonSociale", control.company_name)
    add_content_element(element_company, "numeroSIREN", bdc.get("siren", ""))
    add_content_element(
        element_company, "adresseLigne1", bdc.get("company_address", "")
    )
    add_content_element(element_company, "adresseLigne2", "")
    add_content_element(element_company, "adresseCPostal", "")
    add_content_element(element_company, "adresseVille", "")
    add_content_element(
        element_company, "licenceComNumero", bdc.get("license_number", "")
    )
    add_content_element(
        element_company,
        "licenceComCopieNumero",
        bdc.get("license_copy_number", ""),
    )
    add_content_element(element_company, "licenceIntNumero", "")
    add_content_element(element_company, "licenceIntCopieNumero", "")
    add_content_element(element_company, "numeroNic", "")
    add_content_element(element_company, "typeActivite", "")
    add_content_element(element_company, "modeFonctionnement", "")
    add_content_element(element_company, "contactFonction", "")
    add_content_element(element_company, "contactNom", "")
    add_content_element(element_company, "contactPrenom", "")
    add_content_element(element_company, "contactTitre", "")
    add_content_element(element_company, "dirigeantNom", "")
    add_content_element(element_company, "dirigeantPrenom", "")
    add_content_element(element_company, "pays", "FR - France")
    add_content_element(element_company, "pays_ID", "FR")
    add_content_element(element_company, "resultatGrecoCommunautaire", "")
    add_content_element(element_company, "resultatGrecoInterieure", "")
    add_content_element(element_company, "ent_LicenceComInconnue", "")
    add_content_element(element_company, "ent_LicenceComValidite", "")
    add_content_element(element_company, "ent_AutoType", "")
    add_content_element(element_company, "ent_AutoNum", "")
    add_content_element(element_company, "ent_AutoDate", "")


def process_driver(control, bdc, doc, infractions):
    element_driver = ET.SubElement(doc, "Conducteur")
    ET.SubElement(
        ET.SubElement(element_driver, "id"), "DbValue"
    ).text = "0000000001"

    add_content_element(element_driver, "nom", control.user_last_name)
    add_content_element(element_driver, "prenom", control.user_first_name)
    add_date_element(
        element_driver,
        "naissance",
        datetime.strptime(bdc.get("user_birth_date"), "%Y-%m-%d"),
    )
    add_content_element(
        element_driver, "nationalite", bdc.get("user_nationality", "")
    )

    add_content_element(element_driver, "permisNumero", "")
    add_content_element(element_driver, "permisPays", "")
    add_content_element(element_driver, "permisAutorite", "")
    add_content_element(element_driver, "dCNumero", "")
    add_content_element(element_driver, "dCDateFinValidite", "")
    add_content_element(element_driver, "civilite", "")
    add_content_element(element_driver, "permisCategorie", "")
    add_content_element(element_driver, "octetcndlieunais", "")
    add_content_element(element_driver, "octetcndloca", "")
    add_content_element(element_driver, "octetcndadre", "")
    add_content_element(element_driver, "octetcndcmpl", "")
    add_content_element(element_driver, "octetcndcodp", "")
    add_content_element(element_driver, "octetcndcomu", "")
    add_content_element(element_driver, "datepermis", "")
    add_content_element(element_driver, "fIMO", "")
    add_content_element(element_driver, "fCOS", "")
    add_content_element(element_driver, "aDR", "")
    add_content_element(element_driver, "carteQualification_Numero", "")
    add_content_element(element_driver, "carteQualification_FinValidite", "")
    add_content_element(element_driver, "carteFormation_Disponible", "")
    add_content_element(element_driver, "carteFormation_FinValidite", "")

    if len(infractions) > 0:
        infractions_element = ET.SubElement(
            ET.SubElement(
                ET.SubElement(element_driver, "rInfraction"), "content"
            ),
            "idlist",
        )
        for r in infractions:
            ET.SubElement(
                ET.SubElement(infractions_element, "id"), "DbValue"
            ).text = r.id


def process_vehicle(control, bdc, doc):
    element_vehicle = ET.SubElement(doc, "Vehicule")
    add_content_element(
        element_vehicle, "pays", bdc.get("vehicle_registration_country", "")
    )
    add_content_element(
        element_vehicle, "immatriculation", control.vehicle_registration_number
    )
    add_content_element(element_vehicle, "categoriePoids", "N3")
    add_content_element(element_vehicle, "categorieVehicule", "TRR")
    add_content_element(element_vehicle, "remorque1Immatriculation", "")
    add_content_element(element_vehicle, "remorque2Immatriculation", "")
    add_content_element(element_vehicle, "remorque1Pays", "")
    add_content_element(element_vehicle, "remorque2Pays", "")
    add_content_element(element_vehicle, "proprietaireSIREN", "")
    add_content_element(element_vehicle, "proprietaireRaisonSociale", "")
    add_content_element(element_vehicle, "marchandiseDangereuse", str(0))
    add_content_element(
        element_vehicle, "provenance", bdc.get("mission_address_begin", "")
    )
    add_content_element(
        element_vehicle, "destination", bdc.get("mission_address_end", "")
    )
    add_content_element(element_vehicle, "remorque3Immatriculation", "")
    add_content_element(element_vehicle, "remorque3Pays", "")
    add_content_element(element_vehicle, "typeRemorque", "")
    add_content_element(element_vehicle, "silhouette", "")
    add_content_element(element_vehicle, "remorque1VIN", "")
    add_content_element(element_vehicle, "remorque2VIN", "")
    add_content_element(element_vehicle, "remorque3VIN", "")
    add_content_element(element_vehicle, "marque", "")
    add_content_element(element_vehicle, "remorque1Marque", "")
    add_content_element(element_vehicle, "remorque2Marque", "")
    add_content_element(element_vehicle, "remorque3Marque", "")
    add_content_element(element_vehicle, "octetvehctrpoidvide", "")
    add_content_element(element_vehicle, "octetvehctrptac", "")
    add_content_element(element_vehicle, "octetvehctrptra", "")
    add_content_element(
        element_vehicle, "datePremiereMiseEnCirculation_Value", ""
    )
    add_content_element(
        element_vehicle, "dateProchaineControleTechnique_Value", ""
    )
    add_content_element(element_vehicle, "dateControleRemorque1_Value", "")
    add_content_element(element_vehicle, "dateControleRemorque2_Value", "")
    add_content_element(element_vehicle, "dateControleRemorque3_Value", "")
    add_content_element(element_vehicle, "nbPersonnesOuNatureMarchandise", "")
    add_content_element(element_vehicle, "vE_CatInterRemorque1", "")
    add_content_element(element_vehicle, "vE_CatInterRemorque2", "")
    add_content_element(element_vehicle, "vE_CatInterRemorque3", "")
    add_content_element(
        element_vehicle, "vE_DateCirculationRemorque1_Value", ""
    )
    add_content_element(
        element_vehicle, "vE_DateCirculationRemorque2_Value", ""
    )
    add_content_element(
        element_vehicle, "vE_DateCirculationRemorque3_Value", ""
    )


def process_infractions(control, doc, infractions):
    for r in infractions:
        element_infraction = ET.SubElement(doc, "Infraction")
        add_content_element(element_infraction, "intitule", r.label)
        add_content_element(element_infraction, "flagOk", str(0))
        # TODO debut fin duree norme objet

        add_content_element(element_infraction, "nATINF", r.natinf)
        add_content_element(element_infraction, "inf_ID", r.short_id)
        ET.SubElement(
            ET.SubElement(
                ET.SubElement(element_infraction, "rConducteur"), "id"
            ),
            "DbValue",
        ).text = "0000000001"

        element_recap = ET.SubElement(doc, "RecapInfraction")
        ET.SubElement(
            ET.SubElement(element_recap, "id"), "DbValue"
        ).text = r.id
        add_content_element(element_recap, "nATINF", r.natinf)
        add_content_element(element_recap, "nombre", str(1))
        add_content_element(element_recap, "aVerifier", str(1))
        add_content_element(element_recap, "consignation", str(0))
        add_content_element(element_recap, "immobilisation", str(1))
        add_content_element(element_recap, "nature", r.label)
        add_content_element(element_recap, "rI_ID", r.short_id)

    pass


def get_greco_xml_and_filename(control):
    bdc = control.control_bulletin

    infractions = []
    for idx_r, r in enumerate(control.reported_infractions):
        extra = r.get("extra")
        natinf = extra.get("sanction_code").replace("NATINF ", "")
        short_id = str(idx_r + 1).zfill(4)
        id = f"100100{short_id}"
        infractions.append(
            GrecoInfraction(
                natinf=natinf,
                short_id=short_id,
                id=id,
                label="Label infraction",
            )
        )

    doc = ET.Element("ValueSpace")
    filename = process_control(control, bdc, doc, infractions)
    process_company(control, bdc, doc)
    process_driver(control, bdc, doc, infractions)
    process_vehicle(control, bdc, doc)
    process_infractions(control, doc, infractions)

    xml_data = ET.tostring(doc)
    return (xml_data, filename)


def send_control_as_greco_xml(control):

    (xml_data, file_name) = get_greco_xml_and_filename(control)

    temp_file = tempfile.NamedTemporaryFile(delete=True, suffix=".xml")
    with open(temp_file.name, "wb") as file:
        file.write(xml_data)

    return send_file(
        temp_file.name,
        mimetype="application/xml",
        as_attachment=True,
        download_name=file_name,
    )
