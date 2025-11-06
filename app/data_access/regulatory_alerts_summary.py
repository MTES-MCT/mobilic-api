import graphene


class RegulatoryAlertsSummary(graphene.ObjectType):
    month = graphene.String(description="Mois correspondant aux données.")
    total_nb_alerts = graphene.Int(
        description="Nombre d'alertes total sur le mois."
    )
    total_nb_alerts_previous_month = graphene.Int(
        description="Nombre d'alertes total sur le mois précédent."
    )
