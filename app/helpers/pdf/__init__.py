from xhtml2pdf import pisa
from flask import render_template
from io import BytesIO
from typing import NamedTuple


class Column(NamedTuple):
    name: str
    label: str
    color: str
    format: any = lambda x: x
    secondary: bool = False
    right_border: bool = False
    number: bool = True
    max_width_px: int = None


def generate_pdf_from_template(template_name, **kwargs):
    html = render_template(
        template_name,
        **kwargs,
    )

    output = BytesIO()
    pisa.CreatePDF(html, output)
    output.seek(0)

    return output
