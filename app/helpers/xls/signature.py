import hashlib
import hmac
from io import BytesIO
from zipfile import ZipFile, ZIP_DEFLATED

from defusedxml.ElementTree import parse

from app import app

HMAC_KEY = (
    app.config["HMAC_SIGNING_KEY"].encode()
    if app.config["HMAC_SIGNING_KEY"]
    else None
)
HMAC_PROP_NAME = "Mobilic HMAC"
HMAC_BLOCK_SIZE = 1024
WORKSHEETS_TO_INCLUDE_IN_HMAC = [
    "xl/worksheets/sheet1.xml",
    "xl/worksheets/sheet2.xml",
]


def add_signature(fp):
    if not HMAC_KEY:
        return fp
    new_archive_fp = BytesIO()
    with ZipFile(new_archive_fp, "w", compression=ZIP_DEFLATED) as new_archive:
        with ZipFile(fp, "r") as archive:
            for file_name in archive.namelist():
                if file_name != "docProps/custom.xml":
                    with archive.open(file_name, "r") as f:
                        new_archive.writestr(file_name, f.read())

            signature = compute_hmac(archive, HMAC_KEY)

            with archive.open("docProps/custom.xml", "r") as f:
                xml = parse(f)
                hmac_prop_value = extract_signature_node_from_xml(xml)
                if hmac_prop_value is not None:
                    hmac_prop_value.text = signature

        custom_props_fp = BytesIO()
        xml.write(custom_props_fp, xml_declaration=True, encoding="UTF-8")
        custom_props_fp.seek(0)
        new_archive.writestr("docProps/custom.xml", custom_props_fp.read())

    return new_archive_fp


def compute_hmac(archive, key):
    hmac_signature = hmac.new(key, digestmod=hashlib.sha256)
    for file_name in WORKSHEETS_TO_INCLUDE_IN_HMAC:
        with archive.open(file_name, "r") as f:
            while True:
                block = f.read(HMAC_BLOCK_SIZE)
                if not block:
                    break
                hmac_signature.update(block)
    return hmac_signature.hexdigest()


def extract_signature_node_from_xml(xml):
    root = xml.getroot()
    hmac_prop_value = None
    for child in root:
        if child.attrib.get("name") == HMAC_PROP_NAME:
            hmac_prop_value = child[0]
            break
    return hmac_prop_value
