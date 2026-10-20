import pytest
from pydantic import ValidationError

from vision.ai_contract import TASKS, AnalysisInput, Diagnosis, SendInput, provider_schema


def walk(value):
    if isinstance(value, dict):
        yield value
        for item in value.values():
            yield from walk(item)
    elif isinstance(value, list):
        for item in value:
            yield from walk(item)


def test_openai_strict_schema_recursively_requires_closed_objects():
    schema = provider_schema("openai")
    assert schema["type"] == "object"
    objects = [node for node in walk(schema) if node.get("type") == "object"]
    assert len(objects) >= 2
    for node in objects:
        assert node["additionalProperties"] is False
        assert set(node["required"]) == set(node["properties"])
    assert all("default" not in node for node in walk(schema))


def test_anthropic_schema_omits_unsupported_constraints_but_local_validation_stays_strict():
    schema = provider_schema("anthropic")
    forbidden = {
        "minimum",
        "maximum",
        "minLength",
        "maxLength",
        "minItems",
        "maxItems",
        "uniqueItems",
    }
    assert all(not forbidden.intersection(node) for node in walk(schema))
    assert any(
        "Locally validated constraints" in node.get("description", "") for node in walk(schema)
    )
    with pytest.raises(ValidationError):
        Diagnosis.model_validate(
            {"summary": "x" * 2001, "diagnoses": [], "unknowns": [], "requested_sections": []}
        )


def test_targeted_tasks_have_distinct_substantive_instructions_and_closed_sections():
    assert set(TASKS) == {
        "audit",
        "incident",
        "automation",
        "optimization",
        "availability",
        "template_error",
        "missing_target",
        "mode_conflict",
        "condition_stop",
        "timeout",
        "device_communication",
    }
    assert len({task.instructions for task in TASKS.values()}) == 11
    assert all(len(task.instructions) > 240 for task in TASKS.values())
    assert "remaining" in TASKS["timeout"].instructions
    assert "raw templates" in TASKS["template_error"].instructions.lower()
    assert "refused" in TASKS["mode_conflict"].instructions
    assert "missing current state" in TASKS["missing_target"].instructions
    assert "communication" in TASKS["device_communication"].instructions


def test_defaults_never_enable_diagnostic_data_or_allow_extra_send_fields():
    request = AnalysisInput()
    assert request.profile == "compact" and not request.diagnostic_consent
    with pytest.raises(ValidationError):
        AnalysisInput(sections=["run arbitrary SQL"])
    with pytest.raises(ValidationError):
        SendInput(request_id="a" * 32, digest="b" * 64, target="other")


def test_unknown_citation_related_fields_and_requested_sections_are_not_accepted():
    with pytest.raises(ValidationError):
        Diagnosis.model_validate(
            {"summary": "Limited", "diagnoses": [], "unknowns": [], "requested_sections": ["shell"]}
        )
    with pytest.raises(ValidationError):
        Diagnosis.model_validate(
            {
                "summary": "Limited",
                "diagnoses": [],
                "unknowns": [],
                "requested_sections": [],
                "sql": "SELECT *",
            }
        )
