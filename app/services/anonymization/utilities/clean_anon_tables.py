"""
Script to clean anonymized tables before testing anonymization.
"""

from app import db
from app.models.anonymized import (
    AnonActivity,
    AnonActivityVersion,
    AnonMission,
    AnonMissionEnd,
    AnonMissionValidation,
    AnonLocationEntry,
    AnonEmployment,
    AnonEmail,
    AnonCompany,
    AnonCompanyCertification,
    AnonCompanyStats,
    AnonVehicle,
    AnonCompanyKnownAddress,
    AnonUserAgreement,
    AnonRegulatoryAlert,
    AnonRegulationComputation,
    AnonControllerControl,
    AnonControllerUser,
    AnonTeam,
    AnonTeamAdminUser,
    AnonTeamKnownAddress,
    IdMapping,
)


def clean_anon_tables():
    """Clean all anonymized tables"""
    print("Cleaning anonymized tables...")

    # Delete all data from the mapping table first
    IdMapping.query.delete()

    # Delete data from all anonymized tables
    AnonActivity.query.delete()
    AnonActivityVersion.query.delete()
    AnonMission.query.delete()
    AnonMissionEnd.query.delete()
    AnonMissionValidation.query.delete()
    AnonLocationEntry.query.delete()
    AnonEmployment.query.delete()
    AnonEmail.query.delete()
    AnonCompany.query.delete()
    AnonCompanyCertification.query.delete()
    AnonCompanyStats.query.delete()
    AnonVehicle.query.delete()
    AnonCompanyKnownAddress.query.delete()
    AnonUserAgreement.query.delete()
    AnonRegulatoryAlert.query.delete()
    AnonRegulationComputation.query.delete()
    AnonControllerControl.query.delete()
    AnonControllerUser.query.delete()
    AnonTeam.query.delete()
    AnonTeamAdminUser.query.delete()
    AnonTeamKnownAddress.query.delete()

    # Commit the changes
    db.session.commit()

    print("All anonymized tables have been cleaned!")


if __name__ == "__main__":
    clean_anon_tables()
