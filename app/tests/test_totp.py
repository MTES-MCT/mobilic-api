import pyotp
from cryptography.fernet import Fernet

from app import app, db
from app.domain.totp import (
    decrypt_secret,
    encrypt_secret,
    generate_totp_secret,
    get_or_create_totp_credential,
    get_provisioning_uri,
    verify_totp_code,
)
from app.models import User
from app.models.totp_credential import TotpCredential
from app.seed.factories import UserFactory
from app.tests import BaseTest, test_post_graphql, test_post_graphql_unexposed
from app.tests.helpers import ApiRequests

LOGIN_QUERY = """
    mutation ($email: Email!, $password: String!) {
        auth {
            login (email: $email, password: $password) {
                accessToken
                refreshToken
                totpRequired
            }
        }
    }
"""

VALIDATE_TOTP_LOGIN_MUTATION = """
    mutation ($code: String!) {
        auth {
            validateTotpLogin(code: $code) {
                accessToken
                refreshToken
            }
        }
    }
"""

SETUP_TOTP_MUTATION = """
    mutation {
        account {
            setupTotp {
                provisioningUri
            }
        }
    }
"""

VERIFY_TOTP_MUTATION = """
    mutation ($code: String!) {
        account {
            verifyTotp(code: $code) {
                success
            }
        }
    }
"""


def _create_totp_credential(user, secret, enabled=False):
    """Helper to create a TotpCredential for a user."""
    encrypted = encrypt_secret(secret)
    cred = TotpCredential(
        owner_type="user",
        owner_id=user.id,
        secret=encrypted,
        enabled=enabled,
    )
    db.session.add(cred)
    db.session.commit()
    return cred


class TestTotpCredentialModel(BaseTest):
    def test_totp_credential_creation(self):
        user = UserFactory.create()
        db.session.commit()
        cred = TotpCredential(
            owner_type="user",
            owner_id=user.id,
            secret="ENCRYPTED_SECRET_VALUE",
            enabled=False,
        )
        db.session.add(cred)
        db.session.commit()

        fetched = TotpCredential.query.filter_by(
            owner_type="user", owner_id=user.id
        ).one()
        self.assertEqual(fetched.secret, "ENCRYPTED_SECRET_VALUE")
        self.assertFalse(fetched.enabled)
        self.assertEqual(fetched.failed_attempts, 0)
        self.assertIsNone(fetched.last_failed_at)

    def test_totp_credential_unique_constraint(self):
        user = UserFactory.create()
        db.session.commit()
        cred1 = TotpCredential(
            owner_type="user",
            owner_id=user.id,
            secret="SECRET1",
        )
        db.session.add(cred1)
        db.session.commit()

        cred2 = TotpCredential(
            owner_type="user",
            owner_id=user.id,
            secret="SECRET2",
        )
        db.session.add(cred2)
        with self.assertRaises(Exception):
            db.session.commit()
        db.session.rollback()

    def test_user_totp_credential_relationship(self):
        user = UserFactory.create()
        db.session.commit()
        cred = TotpCredential(
            owner_type="user",
            owner_id=user.id,
            secret="SECRET",
            enabled=True,
        )
        db.session.add(cred)
        db.session.commit()

        db.session.expire_all()
        fetched = User.query.get(user.id)
        self.assertIsNotNone(fetched.totp_credential)
        self.assertEqual(fetched.totp_credential.secret, "SECRET")
        self.assertTrue(fetched.totp_credential.enabled)

    def test_user_without_totp_credential(self):
        user = UserFactory.create()
        db.session.commit()

        db.session.expire_all()
        fetched = User.query.get(user.id)
        self.assertIsNone(fetched.totp_credential)

    def test_enabled_defaults_to_false(self):
        user = UserFactory.create()
        db.session.commit()
        cred = TotpCredential(
            owner_type="user",
            owner_id=user.id,
            secret="SECRET",
        )
        db.session.add(cred)
        db.session.commit()

        fetched = TotpCredential.query.get(cred.id)
        self.assertFalse(fetched.enabled)


class TestTOTPDomain(BaseTest):
    def test_generate_secret_returns_base32(self):
        secret = generate_totp_secret()
        self.assertEqual(len(secret), 32)
        pyotp.TOTP(secret)

    def test_encrypt_decrypt_roundtrip(self):
        secret = generate_totp_secret()
        encrypted = encrypt_secret(secret)
        self.assertNotEqual(encrypted, secret)
        decrypted = decrypt_secret(encrypted)
        self.assertEqual(decrypted, secret)

    def test_verify_valid_code(self):
        secret = generate_totp_secret()
        encrypted = encrypt_secret(secret)
        totp = pyotp.TOTP(secret)
        code = totp.now()
        self.assertTrue(verify_totp_code(encrypted, code))

    def test_verify_invalid_code(self):
        secret = generate_totp_secret()
        encrypted = encrypt_secret(secret)
        self.assertFalse(verify_totp_code(encrypted, "000000"))

    def test_verify_expired_code(self):
        secret = generate_totp_secret()
        encrypted = encrypt_secret(secret)
        totp = pyotp.TOTP(secret)
        code = totp.at(0)
        self.assertFalse(verify_totp_code(encrypted, code))

    def test_provisioning_uri(self):
        secret = generate_totp_secret()
        encrypted = encrypt_secret(secret)
        uri = get_provisioning_uri(encrypted, "admin@example.com")
        self.assertIn("otpauth://totp/", uri)
        self.assertIn("Mobilic", uri)
        self.assertIn("admin%40example.com", uri)

    def test_missing_encryption_key_raises(self):
        original = app.config["TOTP_ENCRYPTION_KEY"]
        app.config["TOTP_ENCRYPTION_KEY"] = None
        try:
            with self.assertRaises(RuntimeError):
                encrypt_secret("test")
        finally:
            app.config["TOTP_ENCRYPTION_KEY"] = original

    def test_multi_key_rotation(self):
        key1 = Fernet.generate_key().decode()
        key2 = Fernet.generate_key().decode()
        original = app.config["TOTP_ENCRYPTION_KEY"]
        app.config["TOTP_ENCRYPTION_KEY"] = f"{key1},{key2}"
        try:
            secret = generate_totp_secret()
            encrypted = encrypt_secret(secret)
            decrypted = decrypt_secret(encrypted)
            self.assertEqual(decrypted, secret)
        finally:
            app.config["TOTP_ENCRYPTION_KEY"] = original

    def test_get_or_create_totp_credential_creates(self):
        user = UserFactory.create()
        db.session.commit()
        cred = get_or_create_totp_credential(user)
        db.session.commit()
        self.assertIsNotNone(cred)
        self.assertEqual(cred.owner_type, "user")
        self.assertEqual(cred.owner_id, user.id)

    def test_get_or_create_totp_credential_returns_existing(self):
        user = UserFactory.create()
        db.session.commit()
        cred1 = get_or_create_totp_credential(user)
        cred1.secret = encrypt_secret(generate_totp_secret())
        db.session.commit()
        cred2 = get_or_create_totp_credential(user)
        self.assertEqual(cred1.id, cred2.id)


class TestSetupTOTPMutation(BaseTest):
    def setUp(self):
        super().setUp()
        self.admin = UserFactory.create(admin=True)
        self.non_admin = UserFactory.create(admin=False)

    def test_setup_totp_returns_provisioning_uri(self):
        response = test_post_graphql_unexposed(
            SETUP_TOTP_MUTATION,
            mock_authentication_with_user=self.admin,
        )
        data = response.json["data"]["account"]["setupTotp"]
        self.assertIsNotNone(data)
        self.assertIn("otpauth://totp/", data["provisioningUri"])
        self.assertIn("Mobilic", data["provisioningUri"])

    def test_setup_totp_saves_encrypted_secret(self):
        test_post_graphql_unexposed(
            SETUP_TOTP_MUTATION,
            mock_authentication_with_user=self.admin,
        )
        cred = TotpCredential.query.filter_by(
            owner_type="user", owner_id=self.admin.id
        ).one_or_none()
        self.assertIsNotNone(cred)
        self.assertIsNotNone(cred.secret)
        self.assertFalse(cred.enabled)

    def test_setup_totp_non_admin_blocked(self):
        response = test_post_graphql_unexposed(
            SETUP_TOTP_MUTATION,
            mock_authentication_with_user=self.non_admin,
        )
        self.assertIsNotNone(response.json.get("errors"))


class TestVerifyTOTPMutation(BaseTest):
    def setUp(self):
        super().setUp()
        self.admin = UserFactory.create(admin=True)
        self.non_admin = UserFactory.create(admin=False)
        secret = generate_totp_secret()
        _create_totp_credential(self.admin, secret, enabled=False)
        self.plain_secret = secret

    def test_verify_totp_activates_2fa(self):
        totp = pyotp.TOTP(self.plain_secret)
        code = totp.now()
        response = test_post_graphql_unexposed(
            VERIFY_TOTP_MUTATION,
            mock_authentication_with_user=self.admin,
            variables={"code": code},
        )
        data = response.json["data"]["account"]["verifyTotp"]
        self.assertTrue(data["success"])
        cred = TotpCredential.query.filter_by(
            owner_type="user", owner_id=self.admin.id
        ).one()
        self.assertTrue(cred.enabled)

    def test_verify_totp_rejects_bad_code(self):
        response = test_post_graphql_unexposed(
            VERIFY_TOTP_MUTATION,
            mock_authentication_with_user=self.admin,
            variables={"code": "000000"},
        )
        self.assertIsNotNone(response.json.get("errors"))
        cred = TotpCredential.query.filter_by(
            owner_type="user", owner_id=self.admin.id
        ).one()
        self.assertFalse(cred.enabled)

    def test_verify_totp_non_admin_blocked(self):
        response = test_post_graphql_unexposed(
            VERIFY_TOTP_MUTATION,
            mock_authentication_with_user=self.non_admin,
            variables={"code": "123456"},
        )
        self.assertIsNotNone(response.json.get("errors"))


class TestLoginWithTOTP(BaseTest):
    def setUp(self):
        super().setUp()
        self.password = "securepass123"
        self.admin = UserFactory.create(admin=True, password=self.password)
        secret = generate_totp_secret()
        _create_totp_credential(self.admin, secret, enabled=True)
        self.plain_secret = secret

    def test_login_totp_user_returns_totp_required(self):
        response = test_post_graphql(
            LOGIN_QUERY,
            variables={
                "email": self.admin.email,
                "password": self.password,
            },
        )
        data = response.json["data"]["auth"]["login"]
        self.assertTrue(data["totpRequired"])
        self.assertIsNotNone(data["accessToken"])
        self.assertIsNone(data["refreshToken"])

    def test_login_non_totp_user_returns_tokens(self):
        normal_user = UserFactory.create(password=self.password)
        db.session.commit()
        response = test_post_graphql(
            LOGIN_QUERY,
            variables={
                "email": normal_user.email,
                "password": self.password,
            },
        )
        data = response.json["data"]["auth"]["login"]
        self.assertFalse(data["totpRequired"])
        self.assertIsNotNone(data["accessToken"])
        self.assertIsNotNone(data["refreshToken"])

    def test_validate_totp_login_returns_full_tokens(self):
        login_response = test_post_graphql(
            LOGIN_QUERY,
            variables={
                "email": self.admin.email,
                "password": self.password,
            },
        )
        temp_token = login_response.json["data"]["auth"]["login"][
            "accessToken"
        ]

        totp = pyotp.TOTP(self.plain_secret)
        code = totp.now()

        response = test_post_graphql(
            VALIDATE_TOTP_LOGIN_MUTATION,
            variables={"code": code},
            headers=[("Authorization", f"Bearer {temp_token}")],
        )
        self.assertIsNone(
            response.json.get("errors"),
            f"Unexpected errors: {response.json.get('errors')}",
        )
        data = response.json["data"]["auth"]["validateTotpLogin"]
        self.assertIsNotNone(data["accessToken"])
        self.assertIsNotNone(data["refreshToken"])

    def test_validate_totp_login_bad_code_rejected(self):
        login_response = test_post_graphql(
            LOGIN_QUERY,
            variables={
                "email": self.admin.email,
                "password": self.password,
            },
        )
        temp_token = login_response.json["data"]["auth"]["login"][
            "accessToken"
        ]

        response = test_post_graphql(
            VALIDATE_TOTP_LOGIN_MUTATION,
            variables={"code": "000000"},
            headers=[("Authorization", f"Bearer {temp_token}")],
        )
        self.assertIsNotNone(response.json.get("errors"))

    def test_validate_totp_login_rate_limited(self):
        login_response = test_post_graphql(
            LOGIN_QUERY,
            variables={
                "email": self.admin.email,
                "password": self.password,
            },
        )
        temp_token = login_response.json["data"]["auth"]["login"][
            "accessToken"
        ]

        for _ in range(5):
            test_post_graphql(
                VALIDATE_TOTP_LOGIN_MUTATION,
                variables={"code": "000000"},
                headers=[("Authorization", f"Bearer {temp_token}")],
            )

        totp = pyotp.TOTP(self.plain_secret)
        response = test_post_graphql(
            VALIDATE_TOTP_LOGIN_MUTATION,
            variables={"code": totp.now()},
            headers=[("Authorization", f"Bearer {temp_token}")],
        )
        self.assertIsNotNone(response.json.get("errors"))

    def test_rate_limit_persists_across_logins(self):
        login_resp = test_post_graphql(
            LOGIN_QUERY,
            variables={
                "email": self.admin.email,
                "password": self.password,
            },
        )
        data = login_resp.json["data"]["auth"]["login"]
        temp_token = data["accessToken"]

        for _ in range(5):
            test_post_graphql(
                VALIDATE_TOTP_LOGIN_MUTATION,
                variables={"code": "000000"},
                headers=[("Authorization", f"Bearer {temp_token}")],
            )

        login_resp2 = test_post_graphql(
            LOGIN_QUERY,
            variables={
                "email": self.admin.email,
                "password": self.password,
            },
        )
        data2 = login_resp2.json["data"]["auth"]["login"]
        temp_token2 = data2["accessToken"]

        totp = pyotp.TOTP(self.plain_secret)
        response = test_post_graphql(
            VALIDATE_TOTP_LOGIN_MUTATION,
            variables={"code": totp.now()},
            headers=[("Authorization", f"Bearer {temp_token2}")],
        )
        self.assertIsNotNone(response.json.get("errors"))
