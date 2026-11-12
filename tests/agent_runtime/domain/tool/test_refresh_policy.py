from agent_runtime.domain.tool.refresh_policy import RefreshPolicy


def test_it_retries_soon_then_backs_off_and_refreshes_slowly_when_all_is_well() -> None:
    policy = RefreshPolicy()

    assert [policy.delay_after(failures) for failures in range(7)] == [60, 5, 10, 20, 40, 60, 60]


def test_it_follows_the_configured_numbers() -> None:
    policy = RefreshPolicy(interval=120, retry_delay=2, max_retry_delay=10)

    assert [policy.delay_after(failures) for failures in range(6)] == [120, 2, 4, 8, 10, 10]
