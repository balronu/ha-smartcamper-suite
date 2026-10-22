from pathlib import Path

from custom_components.smartcamper_suite.const import DOMAIN


def test_suite_coexistence_contract_keeps_domains_and_databases_separate():
    assert DOMAIN == "smartcamper_suite"
    legacy_domains = {"mobile_fuel_stations", "camper_route_planner", "camper_travel_journal"}
    assert DOMAIN not in legacy_domains
    suite_db = Path(".storage/smartcamper_suite.sqlite")
    journal_db = Path(".storage/smartcamper_suite_travel_journal.sqlite")
    assert suite_db != journal_db
    assert suite_db.name != "camper_travel_journal.db"
    assert journal_db.name != "camper_travel_journal.db"
