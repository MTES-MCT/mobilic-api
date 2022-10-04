from collections import namedtuple

DAY = 86400
HOUR = 3600
MINUTE = 60

ComputationResult = namedtuple(
    "ComputationResult", ["success", "extra"], defaults=(False, None)
)

Break = namedtuple("Break", ["start_time", "end_time"])
