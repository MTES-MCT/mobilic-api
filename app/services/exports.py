import math

from app import app


def export_activity_report(
    admin, company_ids, users, min_date, max_date, one_file_by_employee
):
    users = list(users)

    nb_users = len(users)
    nb_days = (max_date - min_date).days
    nb_buckets, bucket_size = get_buckets_params(
        nb_users=nb_users,
        nb_days=nb_days,
        NxD_max=app.config["EXPORT_MAX"],
    )

    app.logger.info(
        f"Export request nb_users={nb_users} nb_days={nb_days} - will split in {nb_buckets} bucket(s) with {bucket_size} employee(s) per bucket"
    )

    from app.helpers.celery import async_export_excel

    users.sort(key=lambda u: u.last_name)
    for i in range(0, nb_users, bucket_size):
        bucket_users = users[i : i + bucket_size]

        async_export_excel.delay(
            admin_id=admin.id,
            user_ids=[user.id for user in bucket_users],
            company_ids=company_ids,
            min_date=min_date,
            max_date=max_date,
            one_file_by_employee=one_file_by_employee,
        )


def get_buckets_params(nb_users, nb_days, NxD_max):
    NxD = nb_users * nb_days

    nb_buckets = math.ceil(NxD / NxD_max)
    bucket_size = math.ceil(nb_users / nb_buckets)

    return nb_buckets, bucket_size
