from flask_admin import Admin, AdminIndexView, expose
from flask_admin.contrib.sqla import ModelView
from flask_admin.contrib.sqla.form import AdminModelConverter
from flask_admin.form import SecureForm
from flask_jwt_extended import current_user
from flask import abort

from app import app, db
from app.helpers.authorization import with_authorization_policy, admin_only
from app.models import User, Activity, Company, Expenditure


class IndexView(AdminIndexView):
    @expose("/")
    @with_authorization_policy(admin_only)
    def index(self):
        return super().index()


class BaseModelView(ModelView):
    named_filter_urls = True
    can_view_details = True
    can_export = True
    ignore_hidden = False
    page_size = 50
    column_display_pk = True
    column_display_all_relations = True
    model_form_converter = AdminModelConverter
    column_exclude_list = (
        "password",
        "_password",
    )
    column_details_exclude_list = ("password", "_password")
    form_excluded_columns = (
        "password",
        "creation_time",
    )
    top_columns = [
        "id",
        "name",
        "first_name",
        "last_name",
        "company",
        "user",
        "type",
    ]
    bottom_columns = ["creation_time"]

    def is_accessible(self):
        return current_user and current_user.admin

    def inaccessible_callback(self):
        abort(404)


admin = Admin(
    app, name="mobilic", index_view=IndexView(), template_mode="bootstrap3"
)


admin.add_view(BaseModelView(User, db.session))
admin.add_view(BaseModelView(Company, db.session))
admin.add_view(BaseModelView(Activity, db.session))
admin.add_view(BaseModelView(Expenditure, db.session))
