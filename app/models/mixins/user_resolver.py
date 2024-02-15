from flask import g


class ResolveUser:
    def resolve_submitter(self, info):
        if not self.submitter_id:
            return None
        return g.dataloaders["users"].load(self.submitter_id)

    def resolve_user(self, info):
        if not self.user_id:
            return None
        return g.dataloaders["users"].load(self.user_id)

    def resolve_dismiss_author(self, info):
        if not self.dismiss_author_id:
            return None
        return g.dataloaders["users"].load(self.dismiss_author_id)
