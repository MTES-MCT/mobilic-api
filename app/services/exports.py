def export_activity_report(
    exporter,
    company_ids,
    users,
    min_date,
    max_date,
    one_file_by_employee,
    file_name=None,
    is_admin=True,
):
    users = list(users)

    from app.helpers.celery import async_export_excel, DEFAULT_FILE_NAME

    async_export_excel.delay(
        exporter_id=exporter.id,
        user_ids=[user.id for user in users],
        company_ids=company_ids,
        min_date=min_date,
        max_date=max_date,
        one_file_by_employee=one_file_by_employee,
        file_name=file_name if file_name is not None else DEFAULT_FILE_NAME,
        is_admin=is_admin,
    )
