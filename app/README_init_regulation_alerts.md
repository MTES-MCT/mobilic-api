# Initialisation of regulatory alerts

## What is it?

It is a process that will erase and recompute every regulatory alerts.

## How to run it?

From any machine connected to the target database, run the command:

```bash
flask init_regulation_alerts [part] [nb_parts] [nb_fork]
```

## How to improve performance?

Running the command locally allow to make some changes that will improve performance.

:warning: These changes should NOT be commited and pushed since they will break the production code.

### Query regulation checks

Replace 

```python
regulation_check = (
    RegulationCheck.query.filter(RegulationCheck.type == type)
    .order_by(desc(RegulationCheck.date_application_start))
    .first()
)
```

by

```python
regulation_check = next(
    (x for x in get_regulation_checks() if x.type == type), None
)
```

:memo: Search for `# To be used locally on init regulation alerts only!` to find where to do it.

### Remove some dependencies

Remove mission history, comments and relationship options.

:memo: Search for `# To be commented locally on init regulation alerts only!` to find which lines to comment.

Update `include_revisions` parameter on `user.query_missions_with_limit` from `True` to `False`.

:memo: Search for `# To be updated locally on init regulation alerts only!` to find where.
