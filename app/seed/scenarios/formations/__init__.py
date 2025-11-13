#
# Files in this package provide functions that can be run to insert data into accounts for formations purposes
# They should be run in a sandbox environment only as they are destructive of past data

import datetime

from app import db
from app.models import (
    Mission,
    Activity,
    ActivityVersion,
    MissionValidation,
    MissionEnd,
    MissionAutoValidation,
    LocationEntry,
    Expenditure,
    ControllerControl,
    RegulationComputation,
    RegulatoryAlert,
    Comment,
)


def _clean_recent_data(employee):
    """
    Removes missions, activities and related data going back 60 days.
    Also removes all alerts and controls for the user
    :param employee: target user
    """
    two_months_ago = datetime.datetime.utcnow() - datetime.timedelta(days=60)
    missions = Mission.query.filter(
        Mission.submitter_id == employee.id,
        Mission.creation_time > two_months_ago,
    ).all()
    mission_ids = [m.id for m in missions]

    activities = Activity.query.filter(
        Activity.mission_id.in_(mission_ids)
    ).all()
    activity_ids = [a.id for a in activities]
    ActivityVersion.query.filter(
        ActivityVersion.activity_id.in_(activity_ids)
    ).delete(synchronize_session=False)
    Activity.query.filter(Activity.id.in_(activity_ids)).delete(
        synchronize_session=False
    )
    Comment.query.filter(Comment.mission_id.in_(mission_ids)).delete(
        synchronize_session=False
    )
    LocationEntry.query.filter(
        LocationEntry.mission_id.in_(mission_ids)
    ).delete(synchronize_session=False)
    Expenditure.query.filter(Expenditure.mission_id.in_(mission_ids)).delete(
        synchronize_session=False
    )
    MissionAutoValidation.query.filter(
        MissionAutoValidation.mission_id.in_(mission_ids)
    ).delete(synchronize_session=False)
    MissionValidation.query.filter(
        MissionValidation.mission_id.in_(mission_ids)
    ).delete(synchronize_session=False)
    MissionEnd.query.filter(MissionEnd.mission_id.in_(mission_ids)).delete(
        synchronize_session=False
    )
    Mission.query.filter(Mission.id.in_(mission_ids)).delete(
        synchronize_session=False
    )

    ControllerControl.query.filter(
        ControllerControl.user_id == employee.id
    ).delete(synchronize_session=False)
    RegulationComputation.query.filter(
        RegulationComputation.user_id == employee.id
    ).delete(synchronize_session=False)
    RegulatoryAlert.query.filter(
        RegulatoryAlert.user_id == employee.id
    ).delete(synchronize_session=False)
    db.session.commit()
