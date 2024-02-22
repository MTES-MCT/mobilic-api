from promise import Promise
from promise.dataloader import DataLoader

from app import db
from app.models import Email, Vehicle, ActivityVersion, RegulatoryAlert


class EmailsInEmploymentLoader(DataLoader):
    def batch_load_fn(self, employment_ids):
        emails = Email.query.filter(
            Email.employment_id.in_(employment_ids)
        ).all()
        return Promise.resolve(
            [
                [email for email in emails if email.employment_id == id]
                for id in employment_ids
            ]
        )


class VehiclesInCompanyLoader(DataLoader):
    def batch_load_fn(self, company_ids):
        vehicles = Vehicle.query.filter(
            Vehicle.company_id.in_(company_ids)
        ).all()
        return Promise.resolve(
            [
                [vehicle for vehicle in vehicles if vehicle.company_id == id]
                for id in company_ids
            ]
        )


class ActivityVersionsInActivityLoader(DataLoader):
    def batch_load_fn(self, activity_ids):
        activity_versions = ActivityVersion.query.filter(
            ActivityVersion.activity_id.in_(activity_ids)
        ).all()
        return Promise.resolve(
            [
                [
                    activity_version
                    for activity_version in activity_versions
                    if activity_version.activity_id == id
                ]
                for id in activity_ids
            ]
        )


def batch_load_simple(class_name, item_ids):
    model_class = db.Model._decl_class_registry.get(class_name)
    items = model_class.query.filter(model_class.id.in_(item_ids)).all()
    items_dict = {item.id: item for item in items}
    return Promise.resolve([items_dict.get(item_id) for item_id in item_ids])


class UserLoader(DataLoader):
    def batch_load_fn(self, user_ids):
        return batch_load_simple(class_name="User", item_ids=user_ids)


class VehicleLoader(DataLoader):
    def batch_load_fn(self, vehicle_ids):
        return batch_load_simple(class_name="Vehicle", item_ids=vehicle_ids)


def batch_load_in_missions(class_name, mission_ids):
    model_class = db.Model._decl_class_registry.get(class_name)
    items = model_class.query.filter(
        model_class.mission_id.in_(mission_ids),
    ).all()
    return Promise.resolve(
        [
            [item for item in items if item.mission_id == id]
            for id in mission_ids
        ]
    )


class CommentsInMissionLoader(DataLoader):
    def batch_load_fn(self, mission_ids):
        return batch_load_in_missions(
            class_name="Comment", mission_ids=mission_ids
        )


class ValidationsInMissionLoader(DataLoader):
    def batch_load_fn(self, mission_ids):
        return batch_load_in_missions(
            class_name="MissionValidation", mission_ids=mission_ids
        )


class ExpendituresInMissionLoader(DataLoader):
    def batch_load_fn(self, mission_ids):
        return batch_load_in_missions(
            class_name="Expenditure", mission_ids=mission_ids
        )


class LocationEntriesInMissionLoader(DataLoader):
    def batch_load_fn(self, mission_ids):
        return batch_load_in_missions(
            class_name="LocationEntry", mission_ids=mission_ids
        )


class ActivitiesInMissionLoader(DataLoader):
    def batch_load_fn(self, mission_ids):
        return batch_load_in_missions(
            class_name="Activity", mission_ids=mission_ids
        )


def batch_load_regulatory_alerts(keys):
    def load_alerts(key):
        user_id, day, submitter_type = key
        alerts = RegulatoryAlert.query.filter(
            RegulatoryAlert.user_id == user_id,
            RegulatoryAlert.day == day,
            RegulatoryAlert.submitter_type == submitter_type,
        ).all()
        return alerts

    return Promise.all([load_alerts(key) for key in keys])
