from enum import Enum
from sqlalchemy.dialects.postgresql import BYTEA
from sqlalchemy import desc
from cached_property import cached_property
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    PrivateFormat,
)
from hashlib import sha1
from functools import lru_cache
from werkzeug.local import LocalProxy

from app.models.base import BaseModel
from app import db
from app.models.utils import enum_column


class SigningKeyOwnerType(str, Enum):
    ROOT = "root"
    MEMBER_STATE = "member_state"
    CARD = "card"


class RSAKey:
    def __init__(
        self,
        modulus,
        modulus_length,
        public_exponent=None,
        private_exponent=None,
    ):
        self.modulus = modulus
        self.modulus_length = modulus_length
        self.public_exponent = public_exponent
        self.private_exponent = private_exponent

    def _transform_message(self, message, exp):
        if len(message) > self.modulus_length:
            raise ValueError(
                f"Message size too long ({len(message)}) for crypto op with RSA of key size {self.modulus_length}"
            )
        if not exp:
            raise ValueError(
                f"Cannot perform crypto-operation in this way because public or private exponent is missing"
            )
        msg_int = int.from_bytes(message, "big")
        transformed = pow(msg_int, exp, self.modulus)
        return transformed.to_bytes(self.modulus_length, "big")

    def decrypt(self, message):
        return self._transform_message(message, self.public_exponent)

    def sign(self, message):
        return self._transform_message(message, self.private_exponent)


class C1BSigningKey(BaseModel, RSAKey):
    __tablename__ = "c1b_signing_key"

    owner_type = enum_column(SigningKeyOwnerType, nullable=False)

    _modulus = db.Column(BYTEA, nullable=False)
    _private_exp = db.Column(BYTEA, nullable=False)
    _public_exp = db.Column(BYTEA, nullable=False)

    modulus_length = db.Column(db.Integer, nullable=False, default=128)

    serial_number = db.Column(db.Integer, nullable=False)

    @classmethod
    def get_current_root_key(cls):
        return (
            cls.query.filter(cls.owner_type == SigningKeyOwnerType.ROOT)
            .order_by(desc(cls.serial_number))
            .limit(1)
            .one_or_none()
        )

    @classmethod
    def get_or_create_current_member_state_key(cls):
        current_ms_key = (
            cls.query.filter(
                cls.owner_type == SigningKeyOwnerType.MEMBER_STATE
            )
            .order_by(desc(cls.serial_number))
            .limit(1)
            .one_or_none()
        )
        if not current_ms_key:
            return cls.generate_new_key(SigningKeyOwnerType.MEMBER_STATE)

    @classmethod
    def get_or_create_current_card_key(cls):
        current_card_key = (
            cls.query.filter(cls.owner_type == SigningKeyOwnerType.CARD)
            .order_by(desc(cls.serial_number))
            .limit(1)
            .one_or_none()
        )
        if not current_card_key:
            return cls.generate_new_key(SigningKeyOwnerType.CARD)

    @cached_property
    def modulus(self):
        return int.from_bytes(self._modulus, "big")

    @cached_property
    def private_exponent(self):
        return int.from_bytes(self._private_exp, "big")

    @cached_property
    def public_exponent(self):
        return int.from_bytes(self._public_exp, "big")

    @classmethod
    def generate_new_key(cls, type, modulus_length=128):
        current_key = (
            cls.query.filter(cls.owner_type == type)
            .order_by(desc(cls.serial_number))
            .limit(1)
            .one_or_none()
        )
        new_serial_number = current_key.serial_number + 1 if current_key else 1

        pub_exp = 65537
        new_key = rsa.generate_private_key(
            public_exponent=pub_exp, key_size=modulus_length * 8
        )
        numbers = new_key.private_numbers()
        priv_exp = numbers.d
        mod = numbers.public_numbers.n

        key = cls(
            owner_type=type,
            _modulus=mod.to_bytes(modulus_length, "big"),
            _public_exp=pub_exp.to_bytes(modulus_length, "big"),
            _private_exp=priv_exp.to_bytes(modulus_length, "big"),
            modulus_length=modulus_length,
            serial_number=new_serial_number,
        )
        db.session.add(key)
        db.session.commit()
        return key

    @property
    def reference(self):
        from app.helpers.tachograph import _int_string_to_bcd

        if self.owner_type == SigningKeyOwnerType.ROOT:
            return (
                b"\xfcMLR"
                + self.serial_number.to_bytes(1, "big")
                + b"\xff\xff\x01"
            )
        if self.owner_type == SigningKeyOwnerType.MEMBER_STATE:
            return (
                b"\xfcMLM"
                + self.serial_number.to_bytes(1, "big")
                + b"\xff\xff\x01"
            )
        serial_number = self.serial_number.to_bytes(4, "big")
        cert_date = _int_string_to_bcd(self.creation_time.strftime("%m%y"))
        return serial_number + cert_date + b"\xff\x01"

    @lru_cache(maxsize=10)
    def certificate(self, authority):
        if not authority:
            raise EnvironmentError("Signing service is unavailable")

        certificate = bytearray()
        certificate.extend(b"\x01")
        certificate.extend(authority.reference)
        certificate.extend(b"\xffMBLIC\x01\xff\xff\xff\xff")

        certificate.extend(self.reference)

        certificate.extend(self.modulus.to_bytes(self.modulus_length, "big"))
        certificate.extend(self.public_exponent.to_bytes(8, "big"))

        certificate_hash = sha1(certificate).digest()
        cert_part_to_sign = certificate[:106]
        cert_part_to_add_in_clear = certificate[106:]

        to_sign = b"\x6A" + cert_part_to_sign + certificate_hash + b"\xBC"

        signed = authority.sign(to_sign)

        return signed + cert_part_to_add_in_clear + authority.reference

    def dump_public_key(self):
        return None


MOBILIC_ROOT_KEY = LocalProxy(lambda: C1BSigningKey.get_current_root_key())
