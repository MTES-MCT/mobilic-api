from dataclasses_json import dataclass_json
from dataclasses import dataclass


@dataclass_json
@dataclass
class SignupData:
    email: str
    password: str
    first_name: str
    last_name: str
    company_id: int
