import json
from pathlib import Path


def test_websocket_matrix_is_machine_readable_and_explicitly_marks_parity():
    matrix = json.loads(Path("docs/phase-2d-websocket-contracts.json").read_text())
    assert matrix["reference"]["commit"] == "11a98f966110d2e70aeb5181b66bc4d97c373623"
    assert len(matrix["stable_commands"]) == 31
    assert len(matrix["suite_commands"]) == 32
    assert matrix["contract_status"]["full_parity"] is False
    assert matrix["mapping"]["update_rating"] == "upsert_rating"
