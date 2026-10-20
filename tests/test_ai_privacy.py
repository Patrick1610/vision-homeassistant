import json

import pytest

from vision.ai_privacy import DiagnosticAliases
from vision.security import Redactor


@pytest.mark.parametrize(
    "text",
    [
        '{"token": "synthetic_plain_value"}',
        "{'api_key': 'synthetic_plain_value'}",
        'password = "synthetic_plain_value with spaces"',
        "{&quot;secret&quot;: &quot;synthetic_plain_value&quot;}",
        r'{"api_key": "synthetic_plain_value"}',
    ],
)
def test_quoted_secret_assignments_are_removed_before_diagnostic_projection(text):
    value = DiagnosticAliases(Redactor()).text(text)
    assert "synthetic_plain_value" not in value


def test_all_identifier_kinds_nested_keys_errors_missing_targets_and_unicode_are_pseudonymous():
    ids = {
        "sensor.private_entity": "entity",
        "device_private": "device",
        "area_private": "area",
        "label_private": "label",
        "light.turn_on": "service",
        "integration_private": "integration",
    }
    aliases = DiagnosticAliases(Redactor(), ids.copy())
    output = aliases.clean(
        {
            "area_private": {
                "entity_id": "sensor.private_entity",
                "device_id": "device_private",
                "area_id": "area_private",
                "label_id": "label_private",
                "service": "light.turn_on",
                "platform": "integration_private",
            },
            "errors": [
                {
                    "message": "sensor&#46;private_entity failed light.turn_on for device_private "
                    "in area_private with label_private integration_private; "
                    "entity_id=light.missing_target area_id=missing_area"
                }
            ],
            "source": r"sensor.\u0070rivate_entity",
        }
    )
    serialized = json.dumps(output)
    assert all(
        identifier not in serialized
        for identifier in (*ids, "light.missing_target", "missing_area")
    )
    assert len(aliases.mapping) == 8
    assert len(set(aliases.by_value.values())) == len(aliases.by_value)


def test_identifier_substrings_do_not_mutate_other_identifiers_or_aliases():
    aliases = DiagnosticAliases(
        Redactor(),
        {
            "sensor.example": "entity",
            "sensor.example_long": "entity",
            "area": "area",
            "area_long": "area",
        },
    )
    text = aliases.text("sensor.example_long sensor.example area_long area")
    assert len(set(text.split())) == 4
    assert all(value in aliases.mapping for value in text.split())


def test_paths_mac_addresses_and_configured_secrets_are_removed():
    value = DiagnosticAliases(Redactor(["synthetic_secret"])).text(
        "At /config/private/file.yaml MAC aa:bb:cc:dd:ee:ff synthetic_secret"
    )
    assert "/config/private" not in value and "aa:bb:cc:dd:ee:ff" not in value
    assert "synthetic_secret" not in value


def test_opaque_configuration_run_context_assignments_and_alias_collisions():
    aliases = DiagnosticAliases(
        Redactor(), {"I1": "device", "config_original": "configuration_entry"}
    )
    first = aliases.text(
        "I1 config_original config_entry_id=config_unknown config_subentry_id=subentry_unknown "
        "run_id=run_unknown context_id=context_unknown"
    )
    assert all(
        value not in first
        for value in (
            "config_original",
            "config_unknown",
            "subentry_unknown",
            "run_unknown",
            "context_unknown",
        )
    )
    original_map = json.loads(json.dumps(aliases.mapping))
    restored = DiagnosticAliases(Redactor(), previous=original_map)
    assert restored.text("I1 config_original") == first.split(" config_entry_id")[0]
    assert restored.mapping == original_map


@pytest.mark.parametrize(
    "text",
    [
        r"{\"api_key\":\"synthetic_plain_value\"}",
        r'{"\u0061pi_key":"synthetic_plain_value"}',
        r"{\\\"token\\\":\\\"synthetic_plain_value\\\"}",
    ],
)
def test_nested_escaped_assignments_and_invalid_unicode_are_bounded(text):
    assert "synthetic_plain_value" not in Redactor().text(text)
    assert Redactor().text("\ud800") == "?"
