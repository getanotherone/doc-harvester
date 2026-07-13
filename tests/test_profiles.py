import json

import pytest

from doc_harvester.profiles import (
    DiscoveryProfile,
    ProfileValidationError,
    list_profiles,
    load_profile,
)


def test_profile_round_trip_and_optional_sections(tmp_path):
    path = tmp_path / "mechanical.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "queries": ["pump catalogue pdf"],
                "priority_terms": ["pump"],
                "priority_domains": [],
                "crawl": {"max_pages": 50},
                "metadata": {"domain": "mechanical"},
            }
        ),
        encoding="utf-8",
    )

    profile = load_profile(path)

    assert profile.name == "mechanical"
    assert profile.queries == ("pump catalogue pdf",)
    assert profile.crawl["max_pages"] == 50
    assert profile.to_dict()["metadata"]["domain"] == "mechanical"


@pytest.mark.parametrize(
    "payload,error",
    [
        ({}, "queries"),
        ({"queries": "not-a-list"}, "array"),
        ({"queries": []}, "at least one"),
        ({"queries": ["ok"], "unexpected": True}, "unknown"),
        ({"schema_version": 2, "queries": ["ok"]}, "schema_version"),
        ({"queries": ["ok"], "crawl": {"max_pages": 0}}, "at least 1"),
        ({"queries": ["ok"], "crawl": {"typo": 10}}, "unknown crawl"),
    ],
)
def test_profile_validation_rejects_invalid_payload(payload, error):
    with pytest.raises(ProfileValidationError, match=error):
        DiscoveryProfile.from_dict("test", payload)


def test_list_and_load_profile_by_name(tmp_path):
    (tmp_path / "valid.json").write_text('{"queries": ["query"]}', encoding="utf-8")
    (tmp_path / "Invalid Name.json").write_text('{"queries": ["query"]}', encoding="utf-8")

    assert list_profiles(tmp_path) == ["valid"]
    assert load_profile("valid", profiles_dir=tmp_path).name == "valid"
