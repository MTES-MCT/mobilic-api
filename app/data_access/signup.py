from app.controllers.utils import request_data_schema


@request_data_schema
class SignupData:
    email: str
    password: str
    first_name: str
    last_name: str
    company_id: int
