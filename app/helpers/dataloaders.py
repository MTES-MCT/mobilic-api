from promise import Promise
from promise.dataloader import DataLoader

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
