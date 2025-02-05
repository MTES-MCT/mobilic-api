from datetime import datetime
import logging
from dateutil.relativedelta import relativedelta
from app import app, db
from app.models.anonymized import IdMapping
from .standalone import StandaloneAnonymizer
from .user_related import UserClassifier

logger = logging.getLogger(__name__)
years = app.config["ANONYMIZATION_THRESHOLD_YEAR"]


def anonymize_expired_data(
    verbose: bool = False, test_mode: bool = False
) -> None:
    if verbose:
        logger.setLevel(logging.DEBUG)

    try:
        cutoff_date = datetime.now() - relativedelta(years=years)
        logger.info(
            f"{'Test mode:' if test_mode else ''}Starting data anonymization process with cut-off date: {cutoff_date.date()}"
        )

        logger.info("Starting user classification phase")
        classifier = UserClassifier(cutoff_date)
        classification = classifier.classify_users_for_anonymization()
        full_anon_users = classification["user_full_anonymization"]
        partial_anon_users = classification["user_partial_anonymization"]

        summary = classifier.get_classification_summary()

        logger.info("Classification summary:")
        logger.info(f"Total inactive users: {summary['total_inactive']}")
        logger.info(
            f"Users ready for full anonymization: {summary['full_anonymization_count']}"
        )
        logger.info(
            f"Users requiring partial anonymization: {summary['partial_anonymization_count']}"
        )

        if test_mode:
            logger.debug("Detailed classification results:")
            logger.debug(
                f"Users ready for full anonymization: {list(classification['user_full_anonymization'])}"
            )
            logger.debug(
                f"Users requiring partial anonymization: {list(classification['user_partial_anonymization'])}"
            )

        logger.info("Start cleaning IdMapping table")
        clean_id_mapping()
        logger.info("Initial IdMapping cleaning complete")

        anonymizer = StandaloneAnonymizer(db.session)
        anonymizer.anonymize_standalone_data(cutoff_date, test_mode)

        logger.info("Process complete: cleaning IdMapping table")
        clean_id_mapping()

        logger.info("Data anonymization completed successfully")

    except Exception as e:
        logger.info("Error occurred: cleaning IdMapping table")
        clean_id_mapping()
        logger.error(f"Error during anonymization: {e}")
        raise


def clean_id_mapping():
    try:
        IdMapping.query.delete()
        db.session.commit()
        logger.info("IdMapping table cleaned successfully")
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error cleaning IdMapping table: {e}")
        raise
