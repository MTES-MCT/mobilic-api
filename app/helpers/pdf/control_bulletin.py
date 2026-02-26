from datetime import datetime

from app.domain.business import get_businesses_display_name
from app.domain.regulations import get_default_business
from app.helpers.pdf import generate_pdf_from_template, generate_pdf_from_list
from app.models import Business
from app.models.controller_control import ControlType

NATINF_METADATA = {
    "11292": {
        "nature": "Contravention de 4ème classe",
        "qualification": "EMPLOI DE SALARIE AU DELA DE LA DUREE QUOTIDIENNE MAXIMALE DE TRAVAIL EFFECTIF - ENTREPRISE DE TRANSPORT ROUTIER",
        "definition": "ART.R.3315-5 AL.1, ART.R.3312-51, ART.D.3312-64, ART.R.3312-34, ART.D.3312-6, ART.R.3312-11, ART.D.3312-31, ART.R.3312-3 C.TRANSPORTS."
    },
    "11289": {
        "nature": "Contravention de 5ème classe",
        "qualification": "EMPLOI, PAR ENTREPRISE DE TRANSPORT ROUTIER DE MARCHANDISES, DE PERSONNEL ROULANT AU DELA DE LA DUREE DE TEMPS DE SERVICE MAXIMALE HEBDOMADAIRE SUR UNE SEMAINE ISOLEE",
        "definition": "ART.R.3315-6 AL.1, ART.R.3312-50, ART.D.3312-45, ART.R.3312-34, ART.D.3312-37 C.TRANSPORTS."
    },
    "20525": {
        "nature": "Contravention de 4ème classe",
        "qualification": "EMPLOI DE PERSONNEL ROULANT SANS REPOS QUOTIDIEN SUFFISANT - ENTREPRISE DE TRANSPORT ROUTIER",
        "definition": "ART.R.3315-5 AL.1, ART.R.3312-13, ART.R.3312-30 AL.5, ART.R.3312-53 2°, ART.R.3312-3, ART.R.3312-34 C.TRANSPORTS."
    },
    "32083": {
        "nature": "Contravention de 5ème classe",
        "qualification": "DEPASSEMENT DE LA DUREE MAXIMALE QUOTIDIENNE DE TRAVAIL DU PERSONNEL ROULANT DE NUIT - ENTREPRISE DE TRANSPORT ROUTIER",
        "definition": "ART.R.3315-3 AL.1, ART.L.3312-1 C.TRANSPORTS. ART.L.3122-5 C.TRAVAIL."
    },
    "13152": {
        "nature": "Contravention de 5ème classe",
        "qualification": "EMPLOI DE SALARIE SANS RESPECT DE LA DUREE MINIMALE DE REPOS HEBDOMADAIRE",
        "definition": "ART.R.3135-2 AL.1, ART.L.3132-1, ART.L.3132-2 C.TRAVAIL."
    },
    "23103": {
        "nature": "Contravention de 4ème classe",
        "qualification": "TRANSPORT ROUTIER DE MARCHANDISES SANS LIVRET INDIVIDUEL DE CONTROLE CONFORME - TRANSPORT SANS HORAIRE FIXE",
        "definition": "ART.R.3315-5 AL.1, ART.R.3312-58 2°, ART.R.3312-34 C.TRANSPORTS. ART.3 ANX.II ARR.MINIST DU 20/07/1998."
    },
    "25666": {
        "nature": "Contravention de 4ème classe",
        "qualification": "TRANSPORT ROUTIER DE PERSONNES SANS LIVRET INDIVIDUEL DE CONTROLE CONFORME",
        "definition": "ART.R.3315-5 AL.1, ART.R.3312-19 2°, ART.R.3312-3 C.TRANSPORTS."
    },
    "35187": {
        "nature": "Contravention de 4ème classe",
        "qualification": "PRISE INSUFFISANTE DE PAUSE PENDANT LE TEMPS DE TRAVAIL PAR PERSONNEL ROULANT D'UNE ENTREPRISE DE TRANSPORT PUBLIC ROUTIER",
        "definition": "ART.R.3315-5 AL.1, ART.L.3312-2 C.TRANSPORTS."
    },
}

def generate_control_bulletin_pdf(control):
    part_one = _generate_part_one(control=control)
    part_two = _generate_part_two(control=control)
    pdf_files = [part_one, part_two]

    pdf = generate_pdf_from_list(pdf_files)
    return pdf

def _generate_part_one(control):
    #Déterminer le(s) type(s) d'activités à afficher dans le BDC
    is_control_mobilic = control.control_type == ControlType.mobilic
    if is_control_mobilic:
        business_ids = list(
            control.control_bulletin.get("employments_business_types").values()
        )
    else:
        business_id = control.control_bulletin.get("business_id", None)
        business = get_default_business(business_id=business_id)
        business_ids = [business.id]
    businesses = Business.query.filter(Business.id.in_(business_ids)).all()
    business_types = ', '.join(list(set([b.transport_type.name for b in businesses])))

    #Signature de l'agent
    #CTT=greco id
    #IT=nom de l'agent
    if not control.controller_user:
        controller_signature = "-"
    else:
        controller = control.controller_user
        controller_signature = controller.greco_id if controller._is_ctt() else f"{controller.last_name} {controller.first_name}"

    birth_date_str = control.control_bulletin.get('user_birth_date')
    formatted_birth_date = datetime.strptime(birth_date_str, "%Y-%m-%d").strftime("%d/%m/%Y") if birth_date_str else "-"

    return generate_pdf_from_template(
        "control_bulletin.html",
        control_bulletin_id=control.reference,
        control_time=control.creation_time,
        control_end_time=control.control_bulletin_update_time,
        control_date=control.creation_time,
        control_location=f"{control.control_bulletin.get('location_lieu')}, {control.control_bulletin.get('location_commune')}",
        controlled_employee_first_name=control.user_first_name,
        controlled_employee_last_name=control.user_last_name,
        controlled_employee_birth_date=formatted_birth_date,
        controlled_employee_nationality=control.control_bulletin.get('user_nationality'),
        controlled_company_siren=control.control_bulletin.get('siren'),
        controlled_company_name=control.company_name,
        controlled_company_address=f"{control.control_bulletin.get('company_address')}",
        transport_type=control.control_bulletin.get("transport_type"),
        articles_nature=control.control_bulletin.get("articles_nature"),
        license_number=control.control_bulletin.get("license_number"),
        license_copy_number=control.control_bulletin.get(
            "license_copy_number"
        ),
        vehicle_registration_number=control.vehicle_registration_number,
        vehicle_registration_country=control.control_bulletin.get(
            "vehicle_registration_country"
        ),
        is_vehicle_immobilized=control.control_bulletin.get(
            "is_vehicle_immobilized"
        ),
        transport_from=control.control_bulletin.get("mission_address_begin"),
        transport_to=control.control_bulletin.get("mission_address_end"),
        observations=control.control_bulletin.get("observation"),
        business_types=business_types,
        controller_signature=controller_signature,
        vehicle_weight=(
            control.control_bulletin.get("real_vehicle_weight")
            if control.control_bulletin
            and control.control_bulletin.get("real_vehicle_weight")
            else "-"
        ) 
    )


def _generate_part_two(control):

    infractions_by_date = {}
    for idx_r, r in enumerate(control.reported_infractions):
        extra = r.get("extra")
        sanction_code = None
        if extra:
            sanction_code = extra.get("sanction_code", "")
        if not sanction_code:
            sanction_code = r.get("sanction", "")
        natinf = sanction_code.replace("NATINF ", "")

        date_str = r.get("date")
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        formatted_date = date_obj.strftime("%d/%m/%y")

        if natinf in infractions_by_date:
            infractions_by_date[natinf].append(formatted_date)
        else:
            infractions_by_date[natinf] = [formatted_date]


    return generate_pdf_from_template(
        "control_bulletin_annexe.html",
        infractions_by_date=infractions_by_date,
        natinf_metadata=NATINF_METADATA
    )
