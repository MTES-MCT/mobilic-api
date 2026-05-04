from app.models import Business


def get_businesses_display_name(business_ids):
    # Filter out None values (e.g., from custom infractions without business_id)
    valid_business_ids = [bid for bid in business_ids if bid is not None]
    if not valid_business_ids:
        return ""
    businesses = Business.query.filter(
        Business.id.in_(valid_business_ids)
    ).all()
    return ", ".join([b.display_name for b in businesses])
