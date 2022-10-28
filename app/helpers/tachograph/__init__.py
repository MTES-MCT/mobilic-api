from io import BytesIO
from typing import NamedTuple, Optional
from datetime import datetime, timezone, date, timedelta
import os
from zipfile import ZIP_DEFLATED, ZipFile

from app.data_access.control_data import compute_history_start_date
from app.domain.work_days import WorkDay, group_user_events_by_day_with_limit
from app.helpers.time import to_datetime
from app.models.activity import ActivityType
from app.helpers.tachograph.signature import (
    verify_signature,
    verify_signatures,
    sign_file,
)
from app.helpers.tachograph.rsa_keys import C1BSigningKey, MOBILIC_ROOT_KEY


# Comprehensive documentation : https://eur-lex.europa.eu/legal-content/FR/TXT/PDF/?uri=CELEX:02016R0799-20200226&from=EN
# Summary : https://docs.google.com/document/d/16q6slqW2SIcpaBjhziVVO_Jb_bcZtLWWbX6ne_SFNrE/edit


MAX_VEHICLE_RECORDS = 200
ACTIVITY_BYTES = 13776


class FileSpec(NamedTuple):
    """
    Unit of storage in driver cards or tachographs. Each file has an ID and a structure that is defined there :
    https://eur-lex.europa.eu/legal-content/FR/TXT/PDF/?uri=CELEX:02016R0799-20200226&from=EN#page=232

    """

    id: bytes
    length: int
    right_fill_with: Optional[bytes] = None
    default_content: bytes = b""
    signable: bool = False

    def __repr__(self):
        matching_file_spec = [
            name
            for (name, spec) in FileSpecs.__dict__.items()
            if type(spec) is FileSpec and spec.id == self.id
        ]
        if matching_file_spec:
            return f"FileSpec<{matching_file_spec[0]}>"
        return f"FileSpec<{self.id}>"


class FileSpecs:
    # https://eur-lex.europa.eu/legal-content/FR/TXT/PDF/?uri=CELEX:02016R0799-20200226&from=EN#page=233
    # Technical information about the physical card (serial number, ...)
    CARD_ICC_IDENTIFICATION = FileSpec(
        b"\x00\x02",
        25,
        right_fill_with=None,
        default_content=bytes(9) + bytes([32] * 8) + bytes(8),
    )

    # https://eur-lex.europa.eu/legal-content/FR/TXT/PDF/?uri=CELEX:02016R0799-20200226&from=EN#page=233
    # Technical information about the card chip (serial_number, ...)
    CARD_CHIP_IDENTIFICATION = FileSpec(
        b"\x00\x05", 8, right_fill_with=None, default_content=bytes(8)
    )

    # https://eur-lex.europa.eu/legal-content/FR/TXT/PDF/?uri=CELEX:02016R0799-20200226&from=EN#page=235
    # Technical information about the card/tachograph software and the file structure
    # 10 bytes length
    # - type of tachograph card (1 byte) : \x01 (driver card)
    # - application major version (1 byte) : \x00 (1st generation)
    # - application minor version (1 byte) : should be \x00 as per the spec but we arbitrarily set it to \x4D ("M") to help identify a Mobilic file.
    # - number of events per type (1 byte) : \x06 (6, but irrelevant for Mobilic)
    # - number of faults per type (1 byte) : \x0c (12, but irrelevant for Mobilic)
    # - space (bytes) dedicated to driver activity records (2 bytes) : \x35\xd0 (13 776, the maximum allowed)
    # - number of vehicle usage records (2 bytes) : \x00\xc8 (200, the maximum allowed)
    # - number of place records (1 byte) : \x70 (112, the maximum allowed)
    APPLICATION_IDENTIFICATION = FileSpec(
        b"\x05\x01",
        10,
        default_content=b"\x01\x00\x4D\x0c\x18"
        + ACTIVITY_BYTES.to_bytes(2, "big")
        + MAX_VEHICLE_RECORDS.to_bytes(2, "big")
        + b"\x70",
        signable=True,
    )

    # https://eur-lex.europa.eu/legal-content/FR/TXT/PDF/?uri=CELEX:02016R0799-20200226&from=EN#page=235
    # Card certificate (PKI)
    CARD_CERTIFICATE = FileSpec(b"\xC1\x00", 194, default_content=bytes(194))

    # https://eur-lex.europa.eu/legal-content/FR/TXT/PDF/?uri=CELEX:02016R0799-20200226&from=EN#page=235
    # Country certificate (PKI)
    CA_CERTIFICATE = FileSpec(b"\xC1\x08", 194, default_content=bytes(194))

    # https://eur-lex.europa.eu/legal-content/FR/TXT/PDF/?uri=CELEX:02016R0799-20200226&from=EN#page=235
    # Domain information about the card (registraton number, issuing authority, ...) and its holder (name, birth date, ...)
    # cf dedicated content generation function for more info about structure
    IDENTIFICATION = FileSpec(b"\x05\x20", 143, signable=True)

    # https://eur-lex.europa.eu/legal-content/FR/TXT/PDF/?uri=CELEX:02016R0799-20200226&from=EN#page=235
    # Timestamp of the latest download of card data
    CARD_DOWNLOAD = FileSpec(
        b"\x05\x0e", 4, default_content=bytes(4), signable=True
    )

    # https://eur-lex.europa.eu/legal-content/FR/TXT/PDF/?uri=CELEX:02016R0799-20200226&from=EN#page=235
    DRIVING_LICENCE_INFO = FileSpec(
        b"\x05\x21",
        53,
        default_content=bytes(1)
        + bytes([32] * 35)
        + bytes(1)
        + bytes([32] * 16),
        signable=True,
    )

    # https://eur-lex.europa.eu/legal-content/FR/TXT/PDF/?uri=CELEX:02016R0799-20200226&from=EN#page=235
    # Latest "events" that occurred (events and faults refer to any error/oddity (technical issue, drive over speed limit, ...)
    # These are auto filled with empty event records (of length 24)
    EVENTS_DATA = FileSpec(
        b"\x05\x02",
        1728,
        right_fill_with=bytes(11) + bytes([32] * 13),
        signable=True,
    )

    # https://eur-lex.europa.eu/legal-content/FR/TXT/PDF/?uri=CELEX:02016R0799-20200226&from=EN#page=235
    # Latest "faults" that occurred (events and faults refer to any error/oddity (technical issue, drive over speed limit, ...)
    # These are auto filled with empty fault records (of length 24)
    FAULTS_DATA = FileSpec(
        b"\x05\x03",
        1152,
        right_fill_with=bytes(11) + bytes([32] * 13),
        signable=True,
    )

    # https://eur-lex.europa.eu/legal-content/FR/TXT/PDF/?uri=CELEX:02016R0799-20200226&from=EN#page=236
    # These are the main data : records of activity changes for the card holder
    # cf dedicated content generation function for more info about structure
    DRIVER_ACTIVITY_DATA = FileSpec(
        b"\x05\x04", 4 + ACTIVITY_BYTES, right_fill_with=b"\x00", signable=True
    )

    # https://eur-lex.europa.eu/legal-content/FR/TXT/PDF/?uri=CELEX:02016R0799-20200226&from=EN#page=236
    # Records of vehicles used by the card
    # cf dedicated content generation function for more info about structure
    # If the whole space (6202) is not filled by vehicle usage records we add empty records (of length 31)
    VEHICLES_USED = FileSpec(
        b"\x05\x05",
        2 + 31 * MAX_VEHICLE_RECORDS,
        right_fill_with=bytes(16) + bytes([32] * 13) + bytes(2),
        default_content=bytes(2),
        signable=True,
    )

    # https://eur-lex.europa.eu/legal-content/FR/TXT/PDF/?uri=CELEX:02016R0799-20200226&from=EN#page=236
    # Records of countries of start/end of service
    # cf dedicated content generation function for more info about structure
    # If the whole space (6202) is not filled by vehicle usage records we add empty records (of length 10)
    PLACES = FileSpec(
        b"\x05\x06",
        1121,
        right_fill_with=bytes(10),
        default_content=bytes(1),
        signable=True,
    )

    # https://eur-lex.europa.eu/legal-content/FR/TXT/PDF/?uri=CELEX:02016R0799-20200226&from=EN#page=236
    # Information about the vehicle (tachograph) that the card is currently inserted in
    CURRENT_USAGE = FileSpec(
        b"\x05\x07",
        19,
        default_content=bytes(6) + bytes([32] * 13),
        signable=True,
    )

    # https://eur-lex.europa.eu/legal-content/FR/TXT/PDF/?uri=CELEX:02016R0799-20200226&from=EN#page=236
    # Information about the latest control that the card was subject to
    CONTROL_ACTIVITY_DATA = FileSpec(
        b"\x05\x08",
        46,
        default_content=bytes(7)
        + bytes([32] * 16)
        + bytes(2)
        + bytes([32] * 13)
        + bytes(8),
        signable=True,
    )

    # https://eur-lex.europa.eu/legal-content/FR/TXT/PDF/?uri=CELEX:02016R0799-20200226&from=EN#page=236
    # Records of specific situations like "ferrying"
    SPECIFIC_CONDITIONS = FileSpec(
        b"\x05\x22", 280, right_fill_with=bytes(5), signable=True
    )


class File:
    def __init__(
        self,
        spec: FileSpec,
        content: bytes = b"",
        signature: Optional[bytes] = None,
    ):
        self.spec = spec
        self.content = content
        self.signature = signature

    def adjust_content(self):
        self.content = check_length_and_right_pad(
            self.content
            if len(self.content) > 0
            else self.spec.default_content or b"",
            self.spec.right_fill_with,
            self.spec.length,
        )

    def sign(self, sk):
        self.adjust_content()
        sign_file(self, sk)

    def __repr__(self):
        return f"<Tachograph File ({repr(self.spec)}) at {id(self)}>"

    # Explained here : https://eur-lex.europa.eu/legal-content/FR/TXT/PDF/?uri=CELEX:02016R0799-20200226&from=EN#page=378
    def verify_signature(self, pk):
        if not self.signature:
            print(f"No signature to verify for file {self.spec}")
            return
        return verify_signature(self.content, self.signature, pk)


def check_length_and_right_pad(bytes_, pad_with, total_length):
    if total_length < len(bytes_):
        raise ValueError(f"Byte sequence exceeds maxium length {total_length}")
    pad_length = total_length - len(bytes_)
    if pad_length == 0:
        return bytes_
    if not pad_with or len(pad_with) == 0:
        raise ValueError("There is nothing to right fill with")
    if pad_length % len(pad_with):
        raise ValueError(
            f"Cannot fill {pad_length} bytes with an undivided sequence of {pad_with}"
        )
    right_padded_bytes = bytearray(bytes_)
    for i in range(pad_length // len(pad_with)):
        right_padded_bytes.extend(pad_with)
    return right_padded_bytes


def dump_file(file):
    """
    According to https://eur-lex.europa.eu/legal-content/FR/TXT/PDF/?uri=CELEX:02016R0799-20200226&from=EN#page=299
    a file is serialized thus :
    - a 5-bytes header specifying the file id and the file length
    - followed by the file content (whose length should match the expected file length)
    """
    file_dump = bytearray()
    # 5-bytes header :
    # - 2 bytes for the file id
    # - 1 byte to specify whether it's the actual file dump (b"\x00") or its digital signature (b"\x01")
    # - 2 bytes for the file length
    header = file.spec.id + b"\x00" + file.spec.length.to_bytes(2, "big")
    file_dump.extend(header)
    file_dump.extend(file.content)
    if file.signature is not None and len(file.signature) > 0:
        signature_header = (
            file.spec.id + b"\x01" + len(file.signature).to_bytes(2, "big")
        )
        file_dump.extend(signature_header)
        file_dump.extend(file.signature)
    return file_dump


def write_tachograph_archive(files):
    """
    The ultimate output, corresponding to .ddd, .c1b or .v1b files, is the direct concatenation of binary file dumps,
    as specified there : https://eur-lex.europa.eu/legal-content/FR/TXT/PDF/?uri=CELEX:02016R0799-20200226&from=EN#page=299.

    What required files should be included in the archive (for it to be readable by any domain software) is not precisely defined and is discussed in the summary (see link at top of file).
    """
    archive = bytearray()
    for file in files:
        archive.extend(dump_file(file))
    return archive


def _serialize_name(name, length):
    # To understand serialization format, see :
    # - https://eur-lex.europa.eu/legal-content/FR/TXT/PDF/?uri=CELEX:02016R0799-20200226&from=EN#page=131
    # - https://eur-lex.europa.eu/legal-content/FR/TXT/PDF/?uri=CELEX:02016R0799-20200226&from=EN#page=182
    name_with_max_length = name
    if len(name) > length - 1:
        name_with_max_length = name[: (length - 1)]

    # first byte (\x01) indicates that we use latin encoding (iso-8859-1)
    return (b"\x01" + name_with_max_length.encode("latin-1", "replace")).ljust(
        length, b"\x20"
    )


def _int_string_to_bcd(i):
    bytes_ = bytearray()
    for index in range(len(i)):
        if index % 2 == 0:
            digit = int(i[index])
            next_digit = int(i[index + 1])
            bytes_.append(digit * 16 + next_digit)
    return bytes_


def _card_like_id(user):
    return f"MBLIC{user.id}"


def build_identification_file(user):
    # 143 bytes ("EF Identification" at https://eur-lex.europa.eu/legal-content/FR/TXT/PDF/?uri=CELEX:02016R0799-20200226&from=EN#page=235), divided in two parts
    # - card identification (65 bytes)
    # - card holder identification (78 bytes)
    content = bytearray()

    # 1. Card identification
    # - first byte is the code of the country member (\x11 for France)
    content.extend(b"\x11")
    # - 16 next bytes are the card number, which is required to be a unique ID by reading softwares (SOLID). We use "MBLIC{mobilic_id}".
    card_like_id = f"{_card_like_id(user)}00"  # len 16
    content.extend(card_like_id.encode())
    # - 36 next bytes give the name of the authority that delivered the card. We use "MOBILIC".
    content.extend(_serialize_name("MOBILIC", 36))
    # - 4 next bytes identify the issue date of the card. We use the creation time for the user.
    content.extend(int(user.creation_time.timestamp()).to_bytes(4, "big"))
    # - 8 next bytes give the validity period of the card (4 bytes for the start time and 4 for the end time). We don't fill these.
    content.extend(bytes(8))

    # 2. Card holder identification
    # - name (36 bytes)
    content.extend(_serialize_name(user.last_name, 36))
    # - first names (36 bytes)
    content.extend(_serialize_name(user.first_name, 36))
    # - birth date (4 bytes), currently only available for FranceConnect users
    birth_date_string = None
    if user.france_connect_info:
        birth_date_string = user.france_connect_info.get("birthdate")
        if birth_date_string:
            birth_date_string = birth_date_string.replace("-", "")
            if len(birth_date_string) != 8 or not birth_date_string.isdigit():
                birth_date_string = None
    content.extend(
        _int_string_to_bcd(birth_date_string)
        if birth_date_string
        else bytes(4)
    )
    # - preferred language (2 bytes), \x66\x72 for french ("fr")
    content.extend(b"\x66\x72")

    return File(spec=FileSpecs.IDENTIFICATION, content=content)


class ActivityChange(NamedTuple):
    type: Optional[ActivityType]
    minutes: int
    mark_as_unknown: bool = False


def build_activity_file(
    work_days, user, first_activity_day, now, start_date=None, end_date=None
):
    # First, since the space is limited on the archive, we may need to restrict the number of work days

    work_days_current_index = len(work_days) - 1
    work_days_with_fills = []
    current_date = end_date or now.date()
    remaining_space = ACTIVITY_BYTES - (2 if current_date == now.date() else 0)

    while remaining_space > 0 and (
        not start_date or current_date >= start_date
    ):
        work_day = (
            work_days[work_days_current_index]
            if work_days_current_index >= 0
            else None
        )
        if work_day and work_day.day == current_date:
            # See https://eur-lex.europa.eu/legal-content/FR/TXT/PDF/?uri=CELEX:02016R0799-20200226&from=EN#page=101
            # this is a conservative estimate
            activity_change_times = set(
                [a.start_time for a in work_day.activities]
            ) | set([a.end_time for a in work_day.activities if a.end_time])
            maximum_activity_changes = len(activity_change_times)
            maximum_required_space = 14 + 2 * maximum_activity_changes
            remaining_space -= maximum_required_space
            if remaining_space >= 0:
                work_days_with_fills.append(work_day)
                work_days_current_index -= 1
                current_date -= timedelta(days=1)

        elif (work_day and work_day.day < current_date) or not work_day:
            remaining_space -= 14
            if remaining_space >= 0:
                work_days_with_fills.append(
                    WorkDay(user=user, day=current_date)
                )
                current_date -= timedelta(days=1)

        else:
            work_days_current_index -= 1

    work_days = list(reversed(work_days_with_fills))
    first_day_in_records = work_days[0].day if work_days else None
    day_counter_starts_at = (
        min(first_activity_day, first_day_in_records)
        if first_day_in_records
        else first_activity_day
    )

    content = bytearray()

    # Spec : https://eur-lex.europa.eu/legal-content/FR/TXT/PDF/?uri=CELEX:02016R0799-20200226&from=EN#page=103
    ## First 2 bytes refer to the offset of the oldest records. For use they always are at the offset 0
    content.extend(bytes(2))
    ## Second 2 bytes refer to the offset of the most recent records. Can only be determined after we wrote everything
    content.extend(bytes(2))

    current_offset = 0
    previous_day_length = 0
    for wd in work_days:
        activity_changes = []
        first_activity = wd.activities[0] if wd.activities else None
        activity_status_at_midnight = None
        midnight = datetime(
            wd.day.year, wd.day.month, wd.day.day, tzinfo=timezone.utc
        )
        if (
            first_activity
            and first_activity.start_time.astimezone(timezone.utc) <= midnight
        ):
            activity_status_at_midnight = first_activity.type
        activity_changes.append(
            ActivityChange(
                type=activity_status_at_midnight,
                minutes=0,
                mark_as_unknown=not activity_status_at_midnight
                and not wd.is_first_mission_overlapping_with_previous_day,
            )
        )
        for index, activity in enumerate(wd.activities):
            start = activity.start_time.astimezone(timezone.utc)
            if start > midnight:
                activity_changes.append(
                    ActivityChange(
                        type=activity.type,
                        minutes=start.hour * 60 + start.minute,
                    )
                )
            end = (
                activity.end_time.astimezone(timezone.utc)
                if activity.end_time
                else None
            )
            if end and end.date() == wd.day:
                next_activity = None
                if index < len(wd.activities) - 1:
                    next_activity = wd.activities[index + 1]
                if (
                    not next_activity
                    or next_activity.start_time != activity.end_time
                ):
                    activity_changes.append(
                        ActivityChange(
                            type=None,
                            minutes=end.hour * 60 + end.minute,
                            mark_as_unknown=not next_activity
                            and not wd.is_last_mission_overlapping_with_next_day,
                        )
                    )

        if wd.day == now.date() and not activity_changes[-1].mark_as_unknown:
            activity_changes.append(
                ActivityChange(
                    type=None,
                    minutes=now.hour * 60 + now.minute,
                    mark_as_unknown=True,
                )
            )

        day_length = 12 + len(activity_changes) * 2

        # Write daily activity record : https://eur-lex.europa.eu/legal-content/FR/TXT/PDF/?uri=CELEX:02016R0799-20200226&from=EN#page=101
        ## - 2 first bytes refer to the previous record length
        content.extend(previous_day_length.to_bytes(2, "big"))
        ## - 2 next bytes refer to the current record length
        content.extend(day_length.to_bytes(2, "big"))
        ## - 4 bytes for the date (unix timestamp)
        content.extend(int(midnight.timestamp()).to_bytes(4, "big"))
        ## - 2 bytes for the work day counter
        content.extend(
            _int_string_to_bcd(
                str((wd.day - day_counter_starts_at).days).rjust(4, "0")
            )
        )
        ## - 2 bytes for the kilometric data (distance made during the day).
        distance = 0
        if (
            not wd.is_first_mission_overlapping_with_previous_day
            and not wd.is_last_mission_overlapping_with_next_day
        ):
            missions_with_activities = set([a.mission for a in wd.activities])
            for mission in missions_with_activities:
                if (
                    mission.start_location
                    and mission.end_location
                    and mission.start_location.kilometer_reading
                    and mission.end_location.kilometer_reading
                ):
                    distance += (
                        mission.end_location.kilometer_reading
                        - mission.start_location.kilometer_reading
                    )
        content.extend(min(distance, 9999).to_bytes(2, "big"))

        ## Write each activity record : https://eur-lex.europa.eu/legal-content/FR/TXT/PDF/?uri=CELEX:02016R0799-20200226&from=EN#page=97
        ## 2 bytes (16 bits), with a lot info set at the bit-level
        for ac in activity_changes:
            bit_string = ""
            ### - First bit : 0 (driver) or 1 (passenger)
            bit_string += "1" if ac.type == ActivityType.SUPPORT else "0"
            ### - Second bit : 0 (solo) or 1 (team) if automatic log, else 0 (unknown) or 1 (manual log)
            ### TODO : set that more precisely
            bit_string += "1" if ac.type == ActivityType.SUPPORT else "0"
            ### - Third bit : 0 (card is inserted, all good) or 1 (card not inserted)
            bit_string += "1" if ac.mark_as_unknown else "0"
            ### - Fourth and fifth bits : activity type
            activity_type_in_bits = "00"
            if ac.type:
                if ac.type in [ActivityType.DRIVE, ActivityType.SUPPORT]:
                    activity_type_in_bits = "11"
                elif ac.type == ActivityType.TRANSFER:
                    activity_type_in_bits = "01"
                else:
                    activity_type_in_bits = "10"
            bit_string += activity_type_in_bits
            ### - Last thirteen bits : minutes since midnight
            bit_string += "{0:b}".format(ac.minutes).rjust(11, "0")

            bytes_ = int(bit_string, 2).to_bytes(2, "big")
            content.extend(bytes_)

        current_offset += previous_day_length
        previous_day_length = day_length

    ## Now that everything is written we set the offset of the most recent records
    content[2:4] = current_offset.to_bytes(2, "big")

    return (
        File(spec=FileSpecs.DRIVER_ACTIVITY_DATA, content=content),
        current_date + timedelta(days=1),
    )


class VehicleRecord:
    def __init__(
        self,
        vehicle_registration_number,
        start_time,
        end_time,
        start_kilometer_reading=None,
        end_kilometer_reading=None,
    ):
        self.vehicle_registration_number = vehicle_registration_number
        self.start_time = start_time
        self.end_time = end_time
        self.start_kilometer_reading = start_kilometer_reading
        self.end_kilometer_reading = end_kilometer_reading


def build_vehicles_file(work_days):
    vehicle_records_to_write = []
    n_vehicle_records = 0

    for work_day in reversed(work_days):
        last_minute_of_day = work_day.end_of_day - timedelta(minutes=1)
        if n_vehicle_records >= MAX_VEHICLE_RECORDS:
            break
        current_mission = None
        current_vehicle = None
        current_vehicle_record = None
        work_day_vehicle_records = []
        for index, activity in enumerate(work_day.activities):
            mission = activity.mission
            if mission.vehicle:
                if (
                    mission != current_mission
                    and mission.vehicle != current_vehicle
                ):
                    current_vehicle_record = VehicleRecord(
                        vehicle_registration_number=mission.vehicle.registration_number,
                        start_time=max(
                            activity.start_time, work_day.start_of_day
                        ),
                        end_time=min(
                            activity.end_time or last_minute_of_day,
                            last_minute_of_day,
                        ),
                        start_kilometer_reading=mission.start_location.kilometer_reading
                        if (
                            index > 0
                            or not work_day.is_first_mission_overlapping_with_previous_day
                        )
                        and mission.start_location
                        else None,
                        end_kilometer_reading=mission.end_location.kilometer_reading
                        if mission.end_location
                        else None,
                    )
                    work_day_vehicle_records.append(current_vehicle_record)
                    n_vehicle_records += 1
                else:
                    current_vehicle_record.end_time = min(
                        activity.end_time or last_minute_of_day,
                        last_minute_of_day,
                    )
                    if mission != current_mission:
                        current_vehicle_record.end_kilometer_reading = (
                            mission.end_location.kilometer_reading
                            if mission.end_location
                            else None
                        )
                if (
                    index == len(work_day.activities) - 1
                    and work_day.is_last_mission_overlapping_with_next_day
                ):
                    current_vehicle_record.end_kilometer_reading = None
                current_mission = mission
                current_vehicle = mission.vehicle

        vehicle_records_to_write.extend(reversed(work_day_vehicle_records))

    vehicle_records_to_write = list(
        reversed(vehicle_records_to_write[:MAX_VEHICLE_RECORDS])
    )
    content = bytearray()

    ## First 2 bytes refer to the index (not the offset) of the newest record.
    content.extend(
        max(len(vehicle_records_to_write) - 1, 0).to_bytes(2, "big")
    )
    for index, vr in enumerate(vehicle_records_to_write):
        ### - 3 bytes for the kilometer reading at the start
        content.extend((vr.start_kilometer_reading or 0).to_bytes(3, "big"))
        ### - 3 bytes for the kilometer reading at the end
        content.extend((vr.end_kilometer_reading or 0).to_bytes(3, "big"))
        ### - 4 bytes for the start time
        content.extend(int(vr.start_time.timestamp()).to_bytes(4, "big"))
        ### - 4 for the end time
        content.extend(int(vr.end_time.timestamp()).to_bytes(4, "big"))
        ### - 1 byte for the nation in which the vehicle is registered (for now it's always \x11 for France)
        content.extend(b"\x11")
        ### - 14 bytes for the registration number
        content.extend(
            _serialize_name(
                vr.vehicle_registration_number.replace(" ", ""), 14
            )
        )
        ### - 2 bytes for the counter of the vehicle unit. We just give the index of the vehicle record, even though this is inconsistent
        content.extend((index + 1).to_bytes(2, "big"))

    return File(spec=FileSpecs.VEHICLES_USED, content=content)


# Spec : https://eur-lex.europa.eu/legal-content/FR/TXT/PDF/?uri=CELEX:02016R0799-20200226&from=EN#page=146
def build_specific_conditions_file(now, start_date, end_date=None):
    start_time = to_datetime(start_date, tz_for_date=timezone.utc)
    end_time = now
    if end_date:
        end_time = min(
            now,
            to_datetime(
                end_date,
                tz_for_date=timezone.utc,
                date_as_end_of_day=True,
            ),
        )

    content = bytearray()
    # Start "hors champ" at the beginning of the earliest work day in the archive
    content.extend(int(start_time.timestamp()).to_bytes(4, "big"))
    content.extend(b"\x01")
    # End "hors champ" at the end time of the latest work day in the archive
    content.extend(int(end_time.timestamp()).to_bytes(4, "big"))
    content.extend(b"\x02")

    return File(spec=FileSpecs.SPECIFIC_CONDITIONS, content=content)


def generate_tachograph_parts(
    user,
    start_date=None,
    end_date=None,
    consultation_scope=None,
    only_activities_validated_by_admin=False,
    with_signatures=True,
    do_not_generate_if_empty=False,
    is_control=False,
    max_reception_time=None,
):
    now = datetime.utcnow()
    first_user_activity = user.first_activity_after(None)
    if not first_user_activity:
        first_user_activity_date = start_date
    else:
        first_user_activity_date = first_user_activity.start_time.astimezone(
            timezone.utc
        ).date()

    if is_control:
        work_days, _ = group_user_events_by_day_with_limit(
            user,
            from_date=start_date,
            until_date=end_date,
            include_dismissed_or_empty_days=True,
            max_reception_time=max_reception_time,
        )
    else:
        work_days, _ = group_user_events_by_day_with_limit(
            user,
            from_date=start_date,
            until_date=end_date,
            tz=timezone.utc,
            only_missions_validated_by_admin=only_activities_validated_by_admin,
            consultation_scope=consultation_scope,
        )

    if not work_days and do_not_generate_if_empty:
        return None

    activity_file, actual_start_date = build_activity_file(
        work_days,
        user,
        first_user_activity_date,
        now,
        start_date=start_date,
        end_date=end_date,
    )

    work_days = [w for w in work_days if w.day >= actual_start_date]

    files = [
        File(spec=FileSpecs.CARD_ICC_IDENTIFICATION),
        File(spec=FileSpecs.CARD_CHIP_IDENTIFICATION),
        File(spec=FileSpecs.APPLICATION_IDENTIFICATION),
        File(spec=FileSpecs.CARD_CERTIFICATE),
        File(spec=FileSpecs.CA_CERTIFICATE),
        build_identification_file(user),
        File(spec=FileSpecs.CARD_DOWNLOAD),
        File(spec=FileSpecs.EVENTS_DATA),
        File(spec=FileSpecs.FAULTS_DATA),
        activity_file,
        build_vehicles_file(work_days),
        File(spec=FileSpecs.PLACES),
        File(spec=FileSpecs.CURRENT_USAGE),
        File(spec=FileSpecs.CONTROL_ACTIVITY_DATA),
        build_specific_conditions_file(
            now, actual_start_date, end_date=end_date
        ),
    ]

    current_card_key = None
    if with_signatures:
        current_card_key = C1BSigningKey.get_or_create_current_card_key()
        current_ms_key = C1BSigningKey.get_or_create_current_member_state_key()

        if not current_card_key or not current_ms_key:
            print("No signing key available for signature")
        else:
            ms_certificate_file = [
                f for f in files if f.spec == FileSpecs.CA_CERTIFICATE
            ][0]
            card_certificate_file = [
                f for f in files if f.spec == FileSpecs.CARD_CERTIFICATE
            ][0]
            ms_certificate_file.content = current_ms_key.certificate(
                MOBILIC_ROOT_KEY
            )
            card_certificate_file.content = current_card_key.certificate(
                current_ms_key
            )

    for file in files:
        file.adjust_content()
        if with_signatures and file.spec.signable:
            file.sign(current_card_key)

    return files


def generate_tachograph_file_name(user):
    now = datetime.utcnow()
    return f'RO_{_card_like_id(user)}{now.strftime("%y%m%d%H%M")}.C1B'


def generate_tachograph_file_name_control(control):
    return f"RO_{_card_like_id(control.user)}_{control.id}.C1B"


def generate_and_export_tachograph_file(
    user, output_dir, start_date=None, end_date=None
):
    files = generate_tachograph_parts(
        user, start_date=start_date, end_date=end_date
    )
    with open(
        f"{os.path.join(output_dir, generate_tachograph_file_name(user))}",
        "wb",
    ) as f:
        f.write(write_tachograph_archive(files))


_file_specs = [v for v in vars(FileSpecs).values() if type(v) is FileSpec]


def parse_tachograph_file(fp, check_signatures=True):
    files = []
    while True:
        file_info = fp.read(5)
        if not file_info:
            break
        file_id = file_info[:2]
        is_signature = file_info[2:3] == b"\x01"
        file_length = int.from_bytes(file_info[-2:], "big")
        content = fp.read(file_length)

        matching_file_spec = [f for f in _file_specs if f.id == file_id]
        if not matching_file_spec:
            print(f"Could not find spec for file id {file_id}")
            continue
        matching_file_spec = matching_file_spec[0]
        if not is_signature:
            files.append(File(spec=matching_file_spec, content=content))
        else:
            file = [f for f in files if f.spec == matching_file_spec][0]
            file.signature = content

    if check_signatures:
        errors = verify_signatures(files)
        if errors:
            print("Detected some signature errors !")
            print(errors)
        else:
            print("Signatures are correct.")

    return files


def get_tachograph_archive_controller(controls, with_signatures):
    archive = BytesIO()
    with ZipFile(archive, "w", compression=ZIP_DEFLATED) as f:
        for control in controls:
            control_max_date = control.qr_code_generation_time.date()
            control_min_date = compute_history_start_date(control_max_date)
            tachograph_data = generate_tachograph_parts(
                control.user,
                start_date=control_min_date,
                end_date=control_max_date,
                only_activities_validated_by_admin=False,
                do_not_generate_if_empty=False,
                is_control=True,
                max_reception_time=control.qr_code_generation_time,
                with_signatures=with_signatures,
            )
            f.writestr(
                generate_tachograph_file_name_control(control),
                write_tachograph_archive(tachograph_data),
            )
    archive.seek(0)
    return archive


def get_tachograph_archive_company(
    users, min_date, max_date, scope, with_signatures
):
    archive = BytesIO()
    with ZipFile(archive, "w", compression=ZIP_DEFLATED) as f:
        for user in users:
            tachograph_data = generate_tachograph_parts(
                user,
                start_date=min_date,
                end_date=max_date,
                consultation_scope=scope,
                only_activities_validated_by_admin=False,
                with_signatures=with_signatures,
                do_not_generate_if_empty=False,
            )
            f.writestr(
                generate_tachograph_file_name(user),
                write_tachograph_archive(tachograph_data),
            )
    archive.seek(0)
    return archive
