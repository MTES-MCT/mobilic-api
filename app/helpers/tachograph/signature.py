from hashlib import sha1
from enum import Enum

from app.helpers.tachograph.rsa_keys import RSAKey, MOBILIC_ROOT_KEY

# Available here : https://dtc.jrc.ec.europa.eu/dtc_erca_official_documentation_dt.php.html
_ERCA_ROOT_PK = bytearray.fromhex(
    "FD45432000FFFF01E980763A444A95250A958782D1D54ACFC323D25F3946B816E92FCF9D32B42A2613D1A363B4E43532A026686329C89663CCC001F7278206B6AB65AD2871848A680F6A57D8FDA1D782C9B5812903EA5B66E2A9BE1D85BDD0FDAE76A46088D71A6176B1F6A98419100424DC56D0846AA3C84390D3517A0F1192DEDFF740924CDBA70000000000010001"
)[8:]

ERCA_ROOT_PK = RSAKey(
    modulus=int.from_bytes(_ERCA_ROOT_PK[:128], "big"),
    modulus_length=128,
    public_exponent=int.from_bytes(_ERCA_ROOT_PK[-8:], "big"),
)

CANDIDATE_ROOT_KEYS = [ERCA_ROOT_PK, MOBILIC_ROOT_KEY]


class FileSignatureErrors(Enum):
    PK_USED_IS_LIKELY_WRONG = "pk_used_is_likely_wrong"
    SIGNATURE_HASH_DOES_NOT_MATCH = "signature_hash_does_not_match"


# cf. https://eur-lex.europa.eu/legal-content/FR/TXT/PDF/?uri=CELEX:02016R0799-20200226&from=EN#page=378
def sign_file(file, sk):
    file_hash = sha1(file.content).digest()
    to_sign = (
        b"\x00\x01"
        + b"\xff" * 90
        + b"\x00"
        + b"\x30\x21\x30\x09\x06\x05\x2B\x0E\x03\x02\x1A\x05\x00\x04\x14"
        + file_hash
    )
    file.signature = sk.sign(to_sign)


# This is well detailed here : https://eur-lex.europa.eu/legal-content/FR/TXT/PDF/?uri=CELEX:02016R0799-20200226&from=EN#page=371
def verify_certificate_and_get_pk(certificate, ca_pk):
    # ca_pk is the 128-bytes RSA public key of the certification authority that signed the certificate :
    # - it effectively is a 136-bytes string (128 bytes for the RSA modulus, and 8 for the exponent)

    # certificate is a 194-bytes string
    certificate_signature = certificate[:128]
    certificate_last_bytes = certificate[128:186]

    decrypted_certificate_signature = ca_pk.decrypt(certificate_signature)

    if (
        decrypted_certificate_signature[0:1] != b"\x6A"
        or decrypted_certificate_signature[-1:] != b"\xBC"
    ):
        raise ValueError(f"Unable to open certificate with the public key")

    decrypted_certificate = (
        decrypted_certificate_signature[1:107] + certificate_last_bytes
    )
    decrypted_certificate_hash = decrypted_certificate_signature[107:127]

    if sha1(decrypted_certificate).digest() != decrypted_certificate_hash:
        raise ValueError("Invalid certificate signature. Hash does not match")

    return RSAKey(
        modulus=int.from_bytes(decrypted_certificate[-136:-8], "big"),
        modulus_length=128,
        public_exponent=int.from_bytes(decrypted_certificate[-8:], "big"),
    )


# Explained here : https://eur-lex.europa.eu/legal-content/FR/TXT/PDF/?uri=CELEX:02016R0799-20200226&from=EN#page=378
def verify_signature(content, signature, pk):
    decoded_signature = pk.decrypt(signature)

    if (
        decoded_signature[:-35] != b"\x00\x01" + b"\xff" * 90 + b"\x00"
        or decoded_signature[-35:-20]
        != b"\x30\x21\x30\x09\x06\x05\x2B\x0E\x03\x02\x1A\x05\x00\x04\x14"
    ):
        return FileSignatureErrors.PK_USED_IS_LIKELY_WRONG
    if decoded_signature[-20:] != sha1(content).digest():
        return FileSignatureErrors.SIGNATURE_HASH_DOES_NOT_MATCH


def verify_signatures(files):
    from app.helpers.tachograph import FileSpecs

    # First we need to retrieve the public key of the device, by opening the member state certificate then the device certificate

    member_state_certificate = [
        f for f in files if f.spec == FileSpecs.CA_CERTIFICATE
    ]
    if not member_state_certificate:
        raise ValueError(
            "Could not verify signatures because of missing member state certificate"
        )
    member_state_certificate = member_state_certificate[0].content

    card_certificate = [
        f for f in files if f.spec == FileSpecs.CARD_CERTIFICATE
    ]
    if not card_certificate:
        raise ValueError(
            "Could not verify signatures because of missing card certificate"
        )
    card_certificate = card_certificate[0].content

    member_state_pk = None
    for root_key in CANDIDATE_ROOT_KEYS:
        try:
            member_state_pk = verify_certificate_and_get_pk(
                member_state_certificate, root_key
            )
            break
        except Exception:
            pass
    if not member_state_pk:
        raise ValueError(
            "Certificate verification failed for all possible root public keys"
        )

    card_pk = verify_certificate_and_get_pk(card_certificate, member_state_pk)

    signature_errors = {}
    for file in files:
        error = file.verify_signature(card_pk)
        if error:
            signature_errors[file.spec] = error

    return signature_errors
