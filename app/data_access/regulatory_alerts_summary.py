import graphene


class AlertDayDetail(graphene.ObjectType):
    day = graphene.Date()
    user_name = graphene.String()
    user_id = graphene.Int()
    other_company_relation = graphene.String(
        description=(
            "Indique si le salarié a aussi travaillé ce jour-là pour une "
            "autre société Mobilic. Valeurs possibles : establishment "
            "(même SIREN = autre établissement de l'entreprise), company "
            "(SIREN différent = autre entreprise), null (aucune autre "
            "activité)."
        )
    )


class AlertsGroup(graphene.ObjectType):
    alerts_type = graphene.String()
    nb_alerts = graphene.Int()
    days = graphene.List(graphene.Date)
    day_details = graphene.List(AlertDayDetail)


class RegulatoryAlertsSummary(graphene.ObjectType):
    has_any_computation = graphene.Boolean(
        description="Indique qu'il n'y a eu aucun calcul d'alertes sur le mois."
    )
    month = graphene.String(description="Mois correspondant aux données.")
    total_nb_alerts = graphene.Int(
        description="Nombre d'alertes total sur le mois."
    )
    total_nb_alerts_previous_month = graphene.Int(
        description="Nombre d'alertes total sur le mois précédent."
    )
    daily_alerts = graphene.List(AlertsGroup)
    weekly_alerts = graphene.List(AlertsGroup)
