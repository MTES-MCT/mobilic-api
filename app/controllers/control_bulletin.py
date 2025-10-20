import graphene
from flask import request

from app import mailer, app, db
from app.helpers.authentication import AuthenticatedMutation, current_user
from app.helpers.authorization import with_authorization_policy
from app.helpers.errors import InvalidParamsError
from app.helpers.mail import MailjetError
from app.helpers.mail_type import EmailType
from app.helpers.pdf.control_bulletin import generate_control_bulletin_pdf
from app.models import ControllerUser
from app.models.controller_control import ControllerControl


class SendControlBulletinEmail(AuthenticatedMutation):
    """
    Envoi du bulletin de contrôle par email aux gestionnaires de l'entreprise.
    """

    class Arguments:
        control_id = graphene.String(
            required=True, description="Identifiant du contrôle"
        )
        admin_emails = graphene.List(
            graphene.String,
            required=True,
            description="Liste des emails des gestionnaires",
        )
        company_name = graphene.String(
            required=True, description="Nom de l'entreprise contrôlée"
        )
        control_date = graphene.String(
            required=False, description="Date du contrôle"
        )
        include_pdf = graphene.Boolean(
            required=False,
            description="Inclure le PDF en pièce jointe",
            default_value=True,
        )

    success = graphene.Boolean()
    emails_sent = graphene.Int()

    @classmethod
    def mutate(
        cls,
        _,
        info,
        control_id,
        admin_emails,
        company_name,
        control_date=None,
        include_pdf=True,
    ):
        if not isinstance(current_user, ControllerUser):
            raise InvalidParamsError(
                "Seuls les contrôleurs peuvent envoyer des bulletins de contrôle"
            )

        if not admin_emails:
            raise InvalidParamsError(
                "Au moins une adresse email de gestionnaire est requise"
            )

        try:
            control = ControllerControl.query.filter(
                ControllerControl.id == int(control_id)
            ).one()
        except Exception:
            raise InvalidParamsError(f"Control {control_id} not found")

        # Construire les informations de lieu
        control_location = ""
        if control.control_bulletin:
            lieu = control.control_bulletin.get("location_lieu", "")
            commune = control.control_bulletin.get("location_commune", "")
            if lieu and commune:
                control_location = f"{lieu}, {commune}"
            elif lieu:
                control_location = lieu
            elif commune:
                control_location = commune

        # Extraire la date et l'heure depuis control_date
        formatted_control_date = ""
        formatted_control_time = ""

        if control_date:
            try:
                from datetime import datetime

                app.logger.info(f"Parsing control_date: {control_date}")

                # Essayer différents formats possibles
                dt = None
                if "T" in control_date:
                    # Format ISO avec T (ex: "2025-10-02T17:31:00")
                    dt = datetime.fromisoformat(
                        control_date.replace("Z", "+00:00")
                    )
                elif " " in control_date:
                    # Format avec espace (ex: "02/10/2025 17:31")
                    if "/" in control_date:
                        dt = datetime.strptime(control_date, "%d/%m/%Y %H:%M")
                    else:
                        dt = datetime.strptime(
                            control_date, "%Y-%m-%d %H:%M:%S"
                        )

                if dt:
                    formatted_control_date = dt.strftime("%d/%m/%Y")
                    formatted_control_time = dt.strftime("%H:%M")
                    app.logger.info(
                        f"Parsed successfully: date={formatted_control_date}, time={formatted_control_time}"
                    )
                else:
                    formatted_control_date = control_date

            except Exception as e:
                app.logger.warning(
                    f"Error parsing control_date {control_date}: {e}"
                )
                # Si on ne peut pas parser, on garde la valeur originale pour la date
                formatted_control_date = control_date
                formatted_control_time = ""

        control_data = {
            "control_id": control_id,
            "company_name": company_name,
            "control_date": formatted_control_date,
            "control_time": formatted_control_time,
            "control_location": control_location,
            "employee_first_name": control.user_first_name or "",
            "employee_last_name": control.user_last_name or "",
            "controller_info": (
                f"{current_user.first_name} {current_user.last_name}"
                if current_user.first_name
                else None
            ),
            "nb_infractions": control.nb_reported_infractions,
        }

        try:
            pdf_content = None
            pdf_filename = None

            if include_pdf:
                try:
                    pdf_content = generate_control_bulletin_pdf(
                        control, current_user, control.user
                    )
                    pdf_filename = (
                        control.bdc_filename
                        or f"Bulletin_de_controle_{control_id}.pdf"
                    )
                    app.logger.info(
                        f"PDF generated for control bulletin {control_id}"
                    )
                except Exception as pdf_error:
                    app.logger.warning(
                        f"Error generating PDF for control bulletin {control_id}: {pdf_error}"
                    )
            else:
                app.logger.info(
                    f"Sending control bulletin {control_id} without PDF (not requested)"
                )

            emails_sent = mailer.send_control_bulletin_email(
                admin_emails,
                control_data,
                bulletin_content=pdf_content,
                bulletin_filename=pdf_filename,
            )

            app.logger.info(
                f"Control bulletin {control_id} sent to {emails_sent} admin(s) of company {company_name}"
            )

            # Mettre à jour le champ send_to_admin
            control.send_to_admin = True
            db.session.commit()

            return SendControlBulletinEmail(
                success=True, emails_sent=emails_sent
            )

        except Exception as e:
            app.logger.exception(
                f"General error for control bulletin {control_id}: {e}"
            )
            raise InvalidParamsError("Error processing control bulletin")
