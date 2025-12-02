import graphene


class AlertsGroup(graphene.ObjectType):
    alerts_type = graphene.String()
    nb_alerts = graphene.Int()
    days = graphene.List(graphene.Date)


class RegulatoryAlertsSummary(graphene.ObjectType):
    has_any_computation = graphene.Boolean(
        description="Indique s'il y a des données pour le mois."
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
