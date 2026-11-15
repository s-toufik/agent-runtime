import pytest

from agent_runtime.adapter.inbound.a2a.turn_options_extension import (
    AUTO_APPROVE_KEY,
    MODEL_KEY,
    RequestedOptions,
    requested_options,
)


def test_the_extension_s_keys_are_read() -> None:
    assert requested_options({MODEL_KEY: "big", AUTO_APPROVE_KEY: True}) == RequestedOptions(
        "big", True
    )


def test_the_short_keys_are_still_read() -> None:
    assert requested_options({"model": "big", "autoApprove": True}) == RequestedOptions("big", True)


def test_the_extension_s_keys_win_over_the_short_ones() -> None:
    metadata = {MODEL_KEY: "big", "model": "small", AUTO_APPROVE_KEY: False, "autoApprove": True}

    assert requested_options(metadata) == RequestedOptions("big", False)


def test_nothing_asked_means_the_defaults() -> None:
    assert requested_options({}) == RequestedOptions("", False)


@pytest.mark.parametrize(
    ("metadata", "expected"),
    [
        ({MODEL_KEY: 42}, RequestedOptions("", False)),
        ({MODEL_KEY: "  big  "}, RequestedOptions("big", False)),
        ({AUTO_APPROVE_KEY: "true"}, RequestedOptions("", False)),
        ({AUTO_APPROVE_KEY: 1}, RequestedOptions("", False)),
    ],
)
def test_values_of_the_wrong_type_are_ignored(metadata, expected) -> None:
    assert requested_options(metadata) == expected
