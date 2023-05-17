from app.helpers.pdf import generate_pdf_from_template


def generate_control_bulletin_pdf(control):
    return generate_pdf_from_template("control_bulletin.html")
