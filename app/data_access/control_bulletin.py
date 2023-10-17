import graphene


class ControlBulletinFields(graphene.ObjectType):
    user_birth_date = graphene.String(required=False)
    user_nationality = graphene.String(required=False)
    siren = graphene.String(required=False)
    company_address = graphene.String(required=False)
    location_department = graphene.String(required=False)
    location_commune = graphene.String(required=False)
    location_lieu = graphene.String(required=False)
    location_id = graphene.Int(required=False)
    vehicle_registration_country = graphene.String(required=False)
    mission_address_begin = graphene.String(required=False)
    mission_address_end = graphene.String(required=False)
    transport_type = graphene.String(required=False)
    articles_nature = graphene.String(required=False)
    license_number = graphene.String(required=False)
    license_copy_number = graphene.String(required=False)
    observation = graphene.String(required=False)
    is_vehicle_immobilized = graphene.Boolean(
        required=False, default_value=False
    )
