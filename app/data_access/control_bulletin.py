import graphene


class ControlBulletinFields(graphene.ObjectType):
    user_birth_date = graphene.String(required=False)
    user_nationality = graphene.String(required=False)
    siren = graphene.String(required=False)
    company_address = graphene.String(required=False)
    vehicle_registration_country = graphene.String(required=False)
    mission_address_begin = graphene.String(required=False)
    mission_address_end = graphene.String(required=False)
    transport_type = graphene.String(required=False)
    articles_nature = graphene.String(required=False)
    license_number = graphene.String(required=False)
    license_copy_number = graphene.String(required=False)
    observation = graphene.String(required=False)

    @staticmethod
    def from_json(json_dct):
        return ControlBulletinFields(
            json_dct.get("user_birth_date"),
            json_dct.get("user_nationality"),
            json_dct.get("siren"),
            json_dct.get("company_address"),
            json_dct.get("vehicle_registration_country"),
            json_dct.get("mission_address_begin"),
            json_dct.get("mission_address_end"),
            json_dct.get("transport_type"),
            json_dct.get("articles_nature"),
            json_dct.get("license_number"),
            json_dct.get("license_copy_number"),
            json_dct.get("observation"),
        )
