from PIL import Image, ImageDraw, ImageFont

from app import db


def get_company_certificate_badge(company_id):
    from app import get_current_certificate
    from app.models import Company

    company = Company.query.get(company_id)
    current_certificate = get_current_certificate(company_id)

    if company:
        company.nb_certificate_badge_request += 1
        db.session.commit()

    if (
        not company
        or not current_certificate
        or not current_certificate.certified
    ):
        # Create a dummy 1x1 blank png
        width, height = 1, 1
        img = Image.new("RGBA", (width, height), (255, 255, 255, 0))
        return img

    badge_image_path = f"app/static/images/certificate/badge-{current_certificate.certification_level.name.lower()}.png"
    img = Image.open(badge_image_path).convert("RGBA")

    draw = ImageDraw.Draw(img)
    text_lines = [
        f"Valide pour l'entreprise {company.usual_name.upper()}",
        f"jusqu'au {current_certificate.expiration_date.strftime('%d/%m/%Y')}",
    ]
    font_path = "fonts/Roboto-Medium.ttf"
    font_size = 20
    font = ImageFont.truetype(font_path, font_size)

    total_text_height = sum(
        draw.textbbox((0, 0), line, font=font)[3]
        - draw.textbbox((0, 0), line, font=font)[1]
        for line in text_lines
    )

    padding_bottom = 60
    image_width, image_height = img.size
    y_text = image_height - total_text_height - padding_bottom

    line_spacing = 8
    # Draw each line centered
    for line in text_lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        x_text = (image_width - text_width) / 2
        draw.text((x_text, y_text), line, font=font, fill=(255, 255, 255, 255))
        y_text += text_height + line_spacing

    return img
