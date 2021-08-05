from datetime import date

from app.helpers.time import VERY_LONG_AGO, VERY_FAR_AHEAD


class WithEmploymentHistory:
    def active_employments_between(
        self, start=None, end=None, include_pending_ones=False
    ):
        end_ = end or date.today()
        start_ = start or VERY_LONG_AGO.date()
        employments = [
            e
            for e in self.employments
            if e.is_not_rejected
            and not e.is_dismissed
            and e.start_date <= end_
            and (e.end_date or VERY_FAR_AHEAD.date()) >= start_
        ]
        if not include_pending_ones:
            return [e for e in employments if e.is_acknowledged]
        return employments

    def active_employments_at(self, date_, include_pending_ones=False):
        return self.active_employments_between(
            date_, date_, include_pending_ones=include_pending_ones
        )
