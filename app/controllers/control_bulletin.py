import graphene

from app import mailer, app, db
from app.helpers.authentication import AuthenticatedMutation, current_user
from app.helpers.authorization import with_authorization_policy
from app.helpers.errors import InvalidParamsError
from app.helpers.pdf.control_bulletin import generate_control_bulletin_pdf
from app.models import ControllerUser, Company
from app.models.controller_control import ControllerControl
from app.helpers.graphene_types import Email
from app.domain.permissions import can_access_control_bulletin


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
            required=False,
            description="Adresses email personnalisées pour les contrôles NoLic",
        )

    success = graphene.Boolean()
    nb_emails_sent = graphene.Int()

    @classmethod
    @with_authorization_policy(
        can_access_control_bulletin,
        get_target_from_args=lambda *args, **kwargs: kwargs["control_id"],
    )
    def mutate(cls, _, info, control_id, admin_emails=None):
        if not isinstance(current_user, ControllerUser):
            raise InvalidParamsError(
                "Seuls les contrôleurs peuvent envoyer des bulletins de contrôle"
            )

        try:
            control = ControllerControl.query.filter(
                ControllerControl.id == int(control_id)
            ).one()
        except Exception:
            raise InvalidParamsError(f"Control {control_id} not found")

        if admin_emails:
            admin_emails_list = admin_emails
        else:
            admin_emails_list = []
            target_company = None
            matching_employment = None

        if not admin_emails and control.user:
            employments = control.user.active_employments_at(
                date_=control.history_end_date
            )

            if employments:
                control_siren = (
                    control.control_bulletin.get("siren")
                    if control.control_bulletin
                    else None
                )
                if control_siren:
                    for employment in employments:
                        if (
                            employment.company
                            and employment.company.siren == control_siren
                        ):
                            matching_employment = employment
                            target_company = employment.company
                            break

                if not target_company and control.company_name:
                    company_name_lower = control.company_name.lower().strip()

                    for employment in employments:
                        if not employment.company:
                            continue

                        company = employment.company
                        legal_name = (company.legal_name or "").lower().strip()
                        usual_name = (company.usual_name or "").lower().strip()

                        if (
                            legal_name
                            and (
                                legal_name in company_name_lower
                                or company_name_lower in legal_name
                            )
                        ) or (
                            usual_name
                            and (
                                usual_name in company_name_lower
                                or company_name_lower in usual_name
                            )
                        ):
                            matching_employment = employment
                            target_company = company
                            break

                if not target_company and len(employments) == 1:
                    matching_employment = employments[0]
                    target_company = employments[0].company

        if not admin_emails and target_company:
            admins = target_company.get_admins(
                start=control.history_end_date, end=control.history_end_date
            )
            for admin in admins:
                if admin.email:
                    admin_emails_list.append(admin.email)

        if not admin_emails_list or len(admin_emails_list) == 0:
            raise InvalidParamsError(
                f"Aucune adresse email de gestionnaire trouvée pour l'entreprise concernée par ce contrôle (SIREN: {control.control_bulletin.get('siren') if control.control_bulletin else 'N/A'})"
            )

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

        formatted_control_date = ""
        formatted_control_time = ""

        control_date = control.qr_code_generation_time or control.creation_time

        if control_date:
            try:
                from datetime import datetime

                app.logger.info(f"Parsing control_date: {control_date}")

                dt = None
                if hasattr(control_date, "strftime"):
                    dt = control_date
                elif isinstance(control_date, str):
                    if "T" in control_date:
                        dt = datetime.fromisoformat(
                            control_date.replace("Z", "+00:00")
                        )
                    elif " " in control_date:
                        if "/" in control_date:
                            dt = datetime.strptime(
                                control_date, "%d/%m/%Y %H:%M"
                            )
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

            except Exception as e:
                app.logger.warning(
                    f"Error parsing control_date {control_date}: {e}"
                )
                formatted_control_date = (
                    str(control_date) if control_date else ""
                )
                formatted_control_time = ""

        company_name = control.company_name or ""

        if not company_name and target_company:
            company_name = (
                target_company.legal_name or target_company.usual_name or ""
            )

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

            try:
                pdf_content = generate_control_bulletin_pdf(control)
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

            nb_emails_sent = mailer.send_control_bulletin_email(
                admin_emails_list,
                control_data,
                bulletin_content=pdf_content,
                bulletin_filename=pdf_filename,
            )

            app.logger.info(
                f"Control bulletin {control_id} sent to {nb_emails_sent} admin(s) of company {company_name or 'Unknown'}"
            )

            control.sent_to_admin = True
            db.session.commit()

            return SendControlBulletinEmail(
                success=True, nb_emails_sent=nb_emails_sent
            )

        except Exception as e:
            app.logger.exception(
                f"General error for control bulletin {control_id}: {e}"
            )
            raise InvalidParamsError("Error processing control bulletin")
