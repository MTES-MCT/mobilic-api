from enum import Enum

GENDER_DESCRIPTION = "Genre de l'utilisateur / utilisatrice"


class Gender(str, Enum):
    FEMALE = "female"
    MALE = "male"
