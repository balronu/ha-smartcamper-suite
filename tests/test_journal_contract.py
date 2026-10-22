from pathlib import Path


def test_journal_websocket_contract_exposes_supported_suite_commands():
    source = Path("custom_components/smartcamper_suite/journal_api.py").read_text()
    expected = {
        "list", "create_trip", "update_trip", "delete_trip", "list_vehicles",
        "diagnostics", "transition_trip", "create_stop", "create_expense",
        "analyze_gpx", "import_gpx", "export_pdf", "list_suggestions",
        "generate_suggestions", "accept_suggestion", "dismiss_suggestion",
        "upsert_overnight", "upsert_rating", "delete_rating",
    }
    actual = {
        line.split("/journal/", 1)[1].split('"', 1)[0]
        for line in source.splitlines()
        if '"type": "smartcamper_suite/journal/' in line
    }
    assert expected <= actual


def test_pdf_builder_is_dependency_free_and_uses_report_sections():
    source = Path("custom_components/smartcamper_suite/journal.py").read_text()
    assert "import reportlab" not in source.lower()
    for section in ("Reiseinformationen", "Aufenthalte", "Zwischenstopps", "Kosten", "GPS-Informationen"):
        assert section in source
