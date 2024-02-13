from promise import Promise
from promise.dataloader import DataLoader

from app import db
from app.models import Email


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
