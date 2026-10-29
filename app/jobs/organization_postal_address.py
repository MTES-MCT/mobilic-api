from app import app, db, siren_api_client
from app.helpers.siren import InaccessibleSirenError, UnavailableSirenAPIError
from app.jobs import log_execution
from app.models import OrganizationalUnitContact


@log_execution
def job_check_organisation_postal_address():
    organisations_query = OrganizationalUnitContact.query.filter(
        OrganizationalUnitContact.siren.isnot(None)
    )

    organisations = organisations_query.all()
    if not organisations:
        app.logger.warning("No organizational units found with a SIREN")
        return

    updates = []

    for organisation in organisations:
        try:
            siren_info = siren_api_client.get_siren_info(
                organisation.siren, True
            )
        except (InaccessibleSirenError, UnavailableSirenAPIError) as error:
            app.logger.warning(
                "Could not fetch SIREN info for organizational unit %s "
                "(SIREN %s): %s",
                organisation.organizational_unit,
                organisation.siren,
                error,
            )
            continue

        etablissements = (
            siren_info.get("etablissements", []) if siren_info else []
        )

        siege = next(
            (
                etablissement
                for etablissement in etablissements
                if etablissement.get("etablissementSiege")
            ),
            None,
        )
        if not siege:
            app.logger.warning(
                "No head-office address found for organizational unit %s "
                "(SIREN %s)",
                organisation.organizational_unit,
                organisation.siren,
            )
            continue

        siren_address = ", ".join(
            part.strip()
            for part in (
                siege.get("adresse"),
                siege.get("adresse2"),
                siege.get("codePostal"),
            )
            if part and part.strip()
        )
        if not siren_address:
            app.logger.warning(
                "Empty head-office address for organizational unit %s "
                "(SIREN %s)",
                organisation.organizational_unit,
                organisation.siren,
            )
            continue

        if organisation.address != siren_address:
            updates.append((organisation, organisation.address, siren_address))

    if updates:
        for organisation, previous_address, address in updates:
            app.logger.info(
                "Address correction for organizational unit %s (SIREN %s): "
                "%r -> %r",
                organisation.organizational_unit,
                organisation.siren,
                previous_address,
                address,
            )
            organisation.address = address
        db.session.commit()
        app.logger.info(
            "Address correction: %s organizational-unit addresses updated",
            len(updates),
        )
    else:
        app.logger.info("All organizational-unit addresses are up to date")
