from app.models import Business


def get_businesses_display_name(business_ids):
    businesses = Business.query.filter(Business.id.in_(business_ids)).all()
    return ", ".join([b.display_name for b in businesses])
