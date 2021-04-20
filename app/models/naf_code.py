from app import db
from app.models.base import BaseModel


class NafCode(BaseModel):
    # The finest-grained code, ex. : 49.42Z (Services de déménagement)
    code = db.Column(db.TEXT, nullable=False, unique=True, index=True)
    label = db.Column(db.TEXT, nullable=False)

    # Coarsest-grained level, ex. : H (TRANSPORTS ET ENTREPOSAGE)
    section_code = db.Column(db.TEXT, nullable=False)
    section_label = db.Column(db.TEXT, nullable=False)

    # The 1st level below the section, ex. : 49 (Transports terrestres et transport par conduites)
    level1_code = db.Column(db.TEXT, nullable=False)
    level1_label = db.Column(db.TEXT, nullable=False)

    # 2nd level below, ex. : 49.4 (Transports routiers de fret et services de déménagement)
    level2_code = db.Column(db.TEXT, nullable=False)
    level2_label = db.Column(db.TEXT, nullable=False)

    # 3rd level below, ex. : 49.42 (Services de déménagement)
    level3_code = db.Column(db.TEXT, nullable=False)
    level3_label = db.Column(db.TEXT, nullable=False)

    @classmethod
    def get_code(cls, code):
        return cls.query.filter(cls.code == code).one_or_none()


x
