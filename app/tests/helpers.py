import re
from collections import namedtuple
from contextlib import contextmanager
from datetime import datetime

from app import db
from app.helpers.time import to_timestamp
from app.models import ControllerUser, User, RegulationCheck
from app.services.get_regulation_checks import get_regulation_checks
from app.tests import (
    test_post_graphql,
    test_post_graphql_protected,
    test_post_graphql_unexposed,
)
from freezegun import freeze_time

INVALID_TOKEN = "Invalid token"
INVALID_API_KEY_MESSAGE = "Invalid API Key"
AUTHENTICATION_ERROR = "Unable to find a valid cookie or authorization header"
AUTHORIZATION_ERROR = "Actor is not authorized to perform the operation"

DBEntryUpdate = namedtuple("DBUnitUpdate", ["model", "before", "after"])
MatchingExpectedChangesWithDbDiff = namedtuple(
    "MatchingExpectedChangesWithDbDiff",
    ["matches", "uncommitted_updates", "unexpected_commits"],
)
ForeignKey = namedtuple("ForeignKey", ["foreign_object_name"])


def _camel_to_snake(obj):
    if type(obj) is dict:
        return {_camel_to_snake(k): v for k, v in obj.items()}
    if type(obj) is list:
        return [_camel_to_snake(item) for item in obj]
    else:
        return re.sub("(.)([A-Z][a-z]+)", r"\1_\2", str(obj)).lower()


def _snake_to_camel(obj):
    if type(obj) is dict:
        return {_snake_to_camel(k): v for k, v in obj.items()}
    if type(obj) is list:
        return [_snake_to_camel(item) for item in obj]
    else:
        first_word, *rest = str(obj).split("_")
        return first_word + "".join(word.title() for word in rest)


def _convert_date_time_to_timestamps(obj):
    if type(obj) is dict:
        return {k: _convert_date_time_to_timestamps(v) for k, v in obj.items()}
    if type(obj) is list:
        return [_convert_date_time_to_timestamps(item) for item in obj]
    if type(obj) is datetime:
        return to_timestamp(obj)
    return obj


def _db_event_to_dict(obj):
    exclude_fields = ["revised_by", "_sa_instance_state", "activities"]
    return {k: v for k, v in obj.__dict__.items() if k not in exclude_fields}


def _remove_foreign_keys(obj):
    return {k: v for k, v in obj.items() if type(v) is not ForeignKey}


def _equals_on_intersect(d1, d2):
    if d1 is None or d2 is None:
        return d1 == d2
    d1_ = _remove_foreign_keys(d1)
    d2_ = _remove_foreign_keys(d2)
    return all([d2_[k] == d1_[k] for k in d1_ if k in d2_])


class ApiRequests:
    log_activity = """
        mutation ($type: ActivityTypeEnum!, $startTime: TimeStamp!, $endTime: TimeStamp, $missionId: Int!, $userId: Int, $context: GenericScalar, $switch: Boolean) {
            activities {
                logActivity(type: $type, startTime: $startTime, endTime: $endTime, missionId: $missionId, userId: $userId, context: $context, switch: $switch) {
                    id
                    type
                    userId
                }
            }
        }
    """

    log_location = """
        mutation logLocation(
            $type: LocationEntryTypeEnum!
            $missionId: Int!
            $geoApiData: GenericScalar
            $manualAddress: String
            $companyKnownAddressId: Int
        ) {
            activities {
                logLocation(
                    missionId: $missionId
                    type: $type
                    geoApiData: $geoApiData
                    manualAddress: $manualAddress
                    companyKnownAddressId: $companyKnownAddressId
                ) {
                    id
                    name
                    alias
                    postalCode
                    city
                }
            }
        }
    """

    create_mission = """
        mutation ($name: String, $companyId: Int!, $context: GenericScalar, $vehicleId: Int, $vehicleRegistrationNumber: String) {
            activities {
                createMission (name: $name, companyId: $companyId, context: $context, vehicleId: $vehicleId, vehicleRegistrationNumber: $vehicleRegistrationNumber) {
                    id
                    name
                }
            }
        }
    """

    end_mission = """
        mutation ($missionId: Int!, $endTime: TimeStamp!, $userId: Int) {
            activities {
                endMission (missionId: $missionId, endTime: $endTime, userId: $userId) {
                    id
                    name
                }
            }
        }
    """

    cancel_mission = """
        mutation ($missionId: Int!, $userId: Int!) {
            activities {
                cancelMission (missionId: $missionId, userId: $userId) {
                    activities {
                      id
                      type
                      missionId
                      startTime
                      endTime
                      userId
                      submitterId
                      lastSubmitterId
                      user {
                        id
                        firstName
                        lastName
                      }
                    }
                }
            }
        }
    """

    cancel_activity = """
        mutation ($activityId: Int!, $context: GenericScalar) {
            activities {
                cancelActivity (activityId: $activityId, context: $context) {
                    success
                }
            }
        }
    """

    edit_activity = """
        mutation ($activityId: Int!, $startTime: TimeStamp, $endTime: TimeStamp, $context: GenericScalar) {
            activities {
                editActivity (activityId: $activityId, startTime: $startTime, endTime: $endTime, context: $context) {
                    id
                    type
                }
            }
        }
    """

    create_account = """
        mutation ($email: String!, $password: Password!, $firstName: String!, $lastName: String!, $inviteToken: String) {
            signUp {
                user(email: $email, password: $password, inviteToken: $inviteToken, firstName: $firstName,
                                                lastName: $lastName) {
                    accessToken
                }
            }
        }
    """

    invite = """
        mutation ($userId: Int, $companyId: Int!, $mail: String) {
            employments {
                createEmployment(userId: $userId, companyId: $companyId, mail: $mail) {
                    id
                }
            }
        }
    """

    redeem_invite = """
        mutation ($token: String!) {
            signUp {
                redeemInvite(token: $token) {
                    id
                }
            }
        }
    """

    change_employee_role = """
        mutation changeEmployeeRole($employmentId: Int!, $hasAdminRights: Boolean!) {
            employments {
              changeEmployeeRole(
                employmentId: $employmentId
                hasAdminRights: $hasAdminRights
              ) {
                id
                hasAdminRights
              }
            }
        }
    """

    terminate_employment = """
        mutation terminateEmployment($employmentId: Int!, $endDate: Date) {
            employments {
              terminateEmployment(employmentId: $employmentId, endDate: $endDate) {
                id
                endDate
              }
            }
        }
    """

    read_control_data = """
    query readControlData($controlId: Int!) {
        controlData(controlId: $controlId) {
          id
          missions {
            activities {
              id
              type
              startTime
              endTime
              userId
            }
          }
        }
    }
    """

    read_control_data_with_alerts = """
    query readControlData($controlId: Int!) {
        controlData(controlId: $controlId) {
          id
          missions {
            activities {
              id
              type
              startTime
              endTime
              userId
            }
          }
          regulationComputationsByDay {
            day
            regulationComputations {
              day
              submitterType
              regulationChecks {
                type
                label
                description
                regulationRule
                unit
                alert {
                  extra
                }
              }
            }
          }
        }
    }
    """

    get_controller_user_info = """
      query controllerUser($id: Int!, $fromDate: Date) {
        controllerUser(id: $id) {
          id
          firstName
          lastName
          email
          controls(fromDate: $fromDate) {
            id
            controlType
            user {
              firstName
              lastName
            }
            qrCodeGenerationTime
            companyName
            vehicleRegistrationNumber
          }
        }
      }
    """

    software_registration = """
      mutation ($clientId: Int!, $usualName: String!, $siren: String!, $siret: String) {
          company {
              softwareRegistration (clientId: $clientId, usualName: $usualName, siren: $siren, siret: $siret) {
                  id
              }
          }
      }
    """

    sync_employment = """
        mutation ($companyId: Int!, $employees: [ThirdPartyEmployee]!) {
            company{
                syncEmployment(companyId: $companyId, employees: $employees) {
                    id
                }
            }
       }
    """

    get_employment_token = """
        query ($employmentId: Int!, $clientId: Int!) {
            employmentToken(employmentId: $employmentId, clientId: $clientId){
                accessToken
                employment{
                    id
                    email
                    user {
                      id
                    }
                }
            }
        }
    """

    generate_employment_token = """
        mutation generateEmploymentToken(
          $clientId: Int!
          $employmentId: Int!
          $invitationToken: String!
        ) {
          generateEmploymentToken(
            clientId: $clientId
            employmentId: $employmentId
            invitationToken: $invitationToken
          ) {
            success
          }
        }
    """

    dismiss_employment_token = """
      mutation dismissEmploymentToken(
          $employmentId: Int!, 
          $clientId: Int!
        ) {
        dismissEmploymentToken(
          employmentId: $employmentId, 
          clientId: $clientId
        ) {
          success
        }
      }
    """

    log_expenditure = """
      mutation logExpenditure(
        $type: ExpenditureTypeEnum!
        $missionId: Int!
        $userId: Int
        $spendingDate: Date!
        $creationTime: TimeStamp
      ) {
        activities {
          logExpenditure(
            type: $type
            missionId: $missionId
            userId: $userId
            spendingDate: $spendingDate
            creationTime: $creationTime
          ) {
            id
          }
        }
      }
    """

    cancel_expenditure = """
      mutation cancelExpenditure($expenditureId: Int!) {
        activities {
          cancelExpenditure(expenditureId: $expenditureId) {
            success
          }
        }
      }
    """

    log_comment = """
      mutation logComment($text: String!, $missionId: Int!) {
        activities {
          logComment(text: $text, missionId: $missionId) {
            id
          }
        }
      }
    """

    cancel_comment = """
      mutation cancelComment($commentId: Int!) {
        activities {
          cancelComment(commentId: $commentId) {
            success
          }
        }
      }
    """

    validate_mission = """
      mutation validateMission(
        $missionId: Int!
        $usersIds: [Int]!
      ) {
        activities {
          validateMission(
            missionId: $missionId
            usersIds: $usersIds
          ) {
            id
          }
        }
      }
    """

    update_mission_vehicle = """
      mutation updateMissionVehicle(
        $missionId: Int!
        $vehicleId: Int
        $vehicleRegistrationNumber: String
      ) {
        activities {
          updateMissionVehicle(
            missionId: $missionId
            vehicleId: $vehicleId
            vehicleRegistrationNumber: $vehicleRegistrationNumber
          ) {
            id
          }
        }
      } 
    """

    change_mission_name = """
      mutation changeMissionName($name: String!, $missionId: Int!) {
        activities {
          changeMissionName(name: $name, missionId: $missionId) {
            id
          }
        }
      }
    """

    create_vehicle = """
      mutation createVehicle(
        $registrationNumber: String!
        $alias: String
        $companyId: Int!
      ) {
        vehicles {
          createVehicle(
            registrationNumber: $registrationNumber
            alias: $alias
            companyId: $companyId
          ) {
            id
          }
        }
      }
    """

    edit_vehicle = """
      mutation($id: Int!, $alias: String) {
        vehicles {
          editVehicle(id: $id, alias: $alias) {
            id
          }
        }
      }
    """

    terminate_vehicle = """
      mutation terminateVehicle($id: Int!) {
        vehicles {
          terminateVehicle(id: $id) {
            success
          }
        }
      }
    """

    create_address = """
      mutation createKnownAddress(
        $geoApiData: GenericScalar
        $manualAddress: String
        $alias: String
        $companyId: Int!
      ) {
        locations {
          createKnownAddress(
            geoApiData: $geoApiData
            manualAddress: $manualAddress
            alias: $alias
            companyId: $companyId
          ) {
            id
          }
        }
      }
    """

    edit_address = """
      mutation editKnownAddress($companyKnownAddressId: Int!, $alias: String) {
        locations {
          editKnownAddress(
            companyKnownAddressId: $companyKnownAddressId
            alias: $alias
          ) {
            id
          }
        }
      }
    """

    terminate_address = """
      mutation terminateKnownAddress($companyKnownAddressId: Int!) {
        locations {
          terminateKnownAddress(companyKnownAddressId: $companyKnownAddressId) {
            success
          }
        }
      }
    """

    edit_company_settings = """
      mutation editCompanySettings(
        $companyId: Int!
        $allowTeamMode: Boolean
        $requireKilometerData: Boolean
        $requireExpenditures: Boolean
        $requireSupportActivity: Boolean
        $allowTransfers: Boolean
        $requireMissionName: Boolean
      ) {
        editCompanySettings(
          companyId: $companyId
          allowTeamMode: $allowTeamMode
          requireKilometerData: $requireKilometerData
          requireExpenditures: $requireExpenditures
          requireSupportActivity: $requireSupportActivity
          allowTransfers: $allowTransfers
          requireMissionName: $requireMissionName
        ) {
          id

        }
      }
    """

    send_invite_reminder = """
      mutation sendInviteReminder($employmentId: Int!) {
        employments {
          sendInvitationReminder(employmentId: $employmentId) {
            success
          }
        }
      }
    """

    query_user = """
      query user($id: Int!){
          user(id: $id) {
              firstName
              lastName
              missions {
                  edges {
                      node {
                          name
                          activities {
                              id
                              type
                              startTime
                              endTime
                              userId
                          }
                          expenditures {
                              id
                              type
                              userId
                          }
                      }
                  }
              }
          }
      }
    """

    query_mission = """
      query mission($id: Int!){
          mission(id: $id) {
              name
              activities {
                  id
                  type
                  startTime
                  endTime
                  userId
              }
              expenditures {
                  id
                  type
                  userId
              }
          }
      }
    """

    query_company = """
      query company($id: Int!){
          company(id: $id) {
              name
              missions {
                  edges {
                    node {
                    id
                    name
                    activities {
                        id
                        type
                        startTime
                        endTime
                        userId
                    }
                    expenditures {
                        id
                        type
                        userId
                    }
                  }
                }
              }
          }
      }
    """

    change_name = """
      mutation changeName(
        $userId: Int!
        $newFirstName: String!
        $newLastName: String!
      ) {
        account {
          changeName(
            userId: $userId
            newFirstName: $newFirstName
            newLastName: $newLastName
          ) {
            id
            firstName
            lastName
          }
        }
      }
    """

    create_team = """
      mutation createTeam(
        $companyId: Int!
        $name: String!
        $userIds: [Int]
        $adminIds: [Int]
        $knownAddressIds: [Int]
        $vehicleIds: [Int]
      ) {
        teams {
          createTeam(
            companyId: $companyId
            name: $name
            userIds: $userIds
            adminIds: $adminIds
            knownAddressIds: $knownAddressIds
            vehicleIds: $vehicleIds
          ) {
            teams {
                id
                name
                creationTime
                adminUsers {
                  id
                  firstName
                  lastName
                }
                users {
                  id
                  firstName
                  lastName
                }
                vehicles {
                  id
                  name
                }
                knownAddresses {
                  id
                  alias
                  name
                  postalCode
                  city
                }
            }
          }
        }
      }
    """

    update_team = """
      mutation updateTeam(
        $teamId: Int!
        $name: String!
        $userIds: [Int]
        $adminIds: [Int]
        $knownAddressIds: [Int]
        $vehicleIds: [Int]
      ) {
        teams {
          updateTeam(
            teamId: $teamId
            name: $name
            userIds: $userIds
            adminIds: $adminIds
            knownAddressIds: $knownAddressIds
            vehicleIds: $vehicleIds
          ) {
            teams {
                id
                name
                creationTime
                adminUsers {
                  id
                  firstName
                  lastName
                }
                users {
                  id
                  firstName
                  lastName
                }
                vehicles {
                  id
                  name
                }
                knownAddresses {
                  id
                  alias
                  name
                  postalCode
                  city
                }
            }
          }
        }
      }
    """

    delete_team = """
      mutation deleteTeam($teamId: Int!) {
        teams {
          deleteTeam(teamId: $teamId) {
            teams {
                id
            }
          }
        }
      }
    """


def _compute_db_model_table_diff(model, old_table_entries, new_table_entries):
    actual_db_updates = []
    for oe in old_table_entries:
        if oe["id"] not in [ne["id"] for ne in new_table_entries]:
            actual_db_updates.append(
                DBEntryUpdate(model=model, before=oe, after=None)
            )
    for ne in new_table_entries:
        matching_old_entries = [
            oe for oe in old_table_entries if oe["id"] == ne["id"]
        ]
        matching_old_entry = (
            matching_old_entries[0] if matching_old_entries else None
        )
        if matching_old_entry != ne:
            actual_db_updates.append(
                DBEntryUpdate(model=model, before=matching_old_entry, after=ne)
            )
    return actual_db_updates


def _match_expected_updates_with_db_diff(expected_db_updates, actual_db_diff):
    matching = {}
    remaining_expected_updates = {**expected_db_updates}
    for expected_update_name, expected_update in expected_db_updates.items():
        actual_updates_on_the_same_object = [
            db_upd
            for db_upd in actual_db_diff
            if db_upd.model == expected_update.model
            and _equals_on_intersect(expected_update.before, db_upd.before)
        ]
        if actual_updates_on_the_same_object:
            if expected_update.before:
                assert (
                    len(actual_updates_on_the_same_object) <= 1
                ), f"Ambiguous update target {expected_update.before} is referring to multiple db entries"
            update_matches = [
                db_upd
                for db_upd in actual_updates_on_the_same_object
                if _equals_on_intersect(expected_update.after, db_upd.after)
            ]
            if update_matches:
                if expected_update.after:
                    assert (
                        len(update_matches) <= 1
                    ), f"Ambiguous update target {expected_update.after} is referring to multiple db entries"
                matching[expected_update_name] = update_matches[0]
                remaining_expected_updates.pop(expected_update_name)
                actual_db_diff.remove(update_matches[0])
    return MatchingExpectedChangesWithDbDiff(
        matches=matching,
        uncommitted_updates=remaining_expected_updates,
        unexpected_commits=actual_db_diff,
    )


@contextmanager
def test_db_changes(expected_changes, watch_models):
    if type(expected_changes) is list:
        expected_changes = {
            str(idx): item for idx, item in enumerate(expected_changes)
        }
    # 1. Query db to get state before the action
    old_db_state = {
        model: [_db_event_to_dict(entry) for entry in model.query.all()]
        for model in watch_models
    }
    db.session.rollback()

    try:
        yield None
        # 2. Do the actual stuff that will impact the db
    finally:
        # 3. Query the db again to get the new state
        db.session.rollback()
        new_db_state = {
            model: [_db_event_to_dict(entry) for entry in model.query.all()]
            for model in watch_models
        }
        db.session.rollback()

        actual_db_diff = []
        for model in watch_models:
            actual_db_diff += _compute_db_model_table_diff(
                model, old_db_state[model], new_db_state[model]
            )

        match_db_changes_result = _match_expected_updates_with_db_diff(
            expected_changes, actual_db_diff
        )
        if match_db_changes_result.uncommitted_updates:
            print("The following expected changes did not happen !")
            print(match_db_changes_result.uncommitted_updates)
        if match_db_changes_result.unexpected_commits:
            print("Unexpected changes to database !")
            print(match_db_changes_result.unexpected_commits)

        assert (
            len(match_db_changes_result.uncommitted_updates.items())
            + len(match_db_changes_result.unexpected_commits)
            == 0
        )

        for expected_change_name, expected_change in expected_changes.items():
            if expected_change.after:
                for field, value in expected_change.after.items():
                    if type(value) is ForeignKey:
                        assert (
                            match_db_changes_result.matches[
                                expected_change_name
                            ].after[field]
                            == match_db_changes_result.matches[
                                value.foreign_object_name
                            ].after["id"]
                        )


def make_authenticated_request(
    time,
    submitter_id,
    query,
    variables,
    request_should_fail_with=None,
    request_by_controller_user=False,
    unexposed_query=False,
):
    formatted_variables = _snake_to_camel(
        _convert_date_time_to_timestamps(variables)
    )
    with freeze_time(time):
        if request_by_controller_user:
            authenticated_user = ControllerUser.query.get(submitter_id)
        else:
            authenticated_user = User.query.get(submitter_id)
        if unexposed_query:
            response = test_post_graphql_unexposed(
                query=query,
                mock_authentication_with_user=authenticated_user,
                variables=formatted_variables,
            )
        else:
            response = test_post_graphql(
                query=query,
                mock_authentication_with_user=authenticated_user,
                variables=formatted_variables,
            )
    db.session.rollback()

    if request_should_fail_with:
        if type(request_should_fail_with) is dict:
            status = request_should_fail_with.get("status")
            if status:
                assert response.status_code == status
    else:
        assert response.status_code == 200

    return response.json


def make_protected_request(
    query,
    variables,
    headers,
    request_should_fail_with=None,
):
    formatted_variables = _snake_to_camel(
        _convert_date_time_to_timestamps(variables)
    )

    response = test_post_graphql_protected(
        query=query, variables=formatted_variables, headers=headers
    )
    db.session.rollback()

    if request_should_fail_with:
        if type(request_should_fail_with) is dict:
            status = request_should_fail_with.get("status")
            if status:
                assert response.status_code == status
    else:
        assert response.status_code == 200

    return response.json


def init_regulation_checks_data():
    regulation_check = RegulationCheck.query.first()
    if not regulation_check:
        regulation_checks = get_regulation_checks()
        for r in regulation_checks:
            insert_regulation_check(r)
        regulation_check = RegulationCheck.query.first()
    return regulation_check


def insert_regulation_check(regulation_data):
    db.session.execute(
        """
            INSERT INTO regulation_check(
              creation_time,
              type,
              label,
              description,
              date_application_start,
              date_application_end,
              regulation_rule,
              variables,
              unit
            )
            VALUES
            (
              NOW(),
              :type,
              :label,
              :description,
              :date_application_start,
              :date_application_end,
              :regulation_rule,
              :variables,
              :unit
            )
            """,
        dict(
            type=regulation_data.type,
            label=regulation_data.label,
            description=regulation_data.description,
            date_application_start=regulation_data.date_application_start,
            date_application_end=regulation_data.date_application_end,
            regulation_rule=regulation_data.regulation_rule,
            variables=regulation_data.variables,
            unit=regulation_data.unit,
        ),
    )
