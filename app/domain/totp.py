import pyotp
from cryptography.fernet import Fernet, MultiFernet
from flask import current_app

from app import db
from app.models.totp_credential import TotpCredential


def _get_fernet():
    key = current_app.config.get("TOTP_ENCRYPTION_KEY")
    if not key:
        raise RuntimeError("TOTP_ENCRYPTION_KEY is not set in config")
    keys = [k.strip() for k in key.split(",") if k.strip()]
    if len(keys) == 1:
        return Fernet(keys[0].encode())
    return MultiFernet([Fernet(k.encode()) for k in keys])


def generate_totp_secret():
    return pyotp.random_base32()


def encrypt_secret(secret):
    f = _get_fernet()
    return f.encrypt(secret.encode()).decode()


def decrypt_secret(encrypted_secret):
    f = _get_fernet()
    return f.decrypt(encrypted_secret.encode()).decode()


def verify_totp_code(encrypted_secret, code):
    secret = decrypt_secret(encrypted_secret)
    totp = pyotp.TOTP(secret)
    return totp.verify(code, valid_window=1)


def get_provisioning_uri(encrypted_secret, email):
    secret = decrypt_secret(encrypted_secret)
    totp = pyotp.TOTP(secret)
    return totp.provisioning_uri(name=email, issuer_name="Mobilic")


def get_or_create_totp_credential(owner):
    """Get existing or create new TotpCredential for owner.

    Args:
        owner: a User or ControllerUser instance.
    """
    owner_type = owner.__tablename__
    cred = TotpCredential.query.filter_by(
        owner_type=owner_type, owner_id=owner.id
    ).one_or_none()
    if not cred:
        cred = TotpCredential(
            owner_type=owner_type,
            owner_id=owner.id,
            secret="",
            enabled=False,
        )
        db.session.add(cred)
    return cred
