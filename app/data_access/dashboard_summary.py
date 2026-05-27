import graphene


class DashboardSummary(graphene.ObjectType):
    active_missions_count = graphene.Int(
        description="Nombre de missions en cours (non terminées)"
    )
    pending_validations_count = graphene.Int(
        description="Nombre de missions en attente de validation gestionnaire"
    )
    pending_invitations_count = graphene.Int(
        description=("Nombre d'invitations de salariés en attente")
    )
    inactive_employees_count = graphene.Int(
        description="Nombre de salariés n'ayant pas lancé Mobilic aujourd'hui"
    )
    auto_validated_missions_count = graphene.Int(
        description=("Nombre de missions validées automatiquement")
    )
    pending_invitation_employment_ids = graphene.List(
        graphene.Int,
        description=("IDs des emplois avec invitation en attente"),
    )
    has_any_mission_this_week = graphene.Boolean(
        description=(
            "Vrai si au moins une mission a une activité enregistrée "
            "depuis le début de la semaine en cours"
        )
    )
