import bootstrap.configuration.settings as settings_module
from bootstrap.configuration.settings import ProcessSettings


def test_for_role_uses_explicit_env_overrides(monkeypatch) -> None:
    monkeypatch.setattr(settings_module.dotenv, "load_dotenv", lambda: None)
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("CONFIGURATION_DIR", "/custom/config")
    monkeypatch.setenv("GUARDRAIL_ENABLED", "true")

    settings = ProcessSettings.for_role("agent-runtime")

    assert settings.role == "agent-runtime"
    assert settings.environment == "prod"
    assert str(settings.configuration_directory) == "/custom/config"
    assert settings.guardrail_enabled is True


def test_for_role_falls_back_to_defaults_when_nothing_is_set(monkeypatch) -> None:
    monkeypatch.setattr(settings_module.dotenv, "load_dotenv", lambda: None)
    for key in ("APP_ENV", "CONFIGURATION_DIR", "GUARDRAIL_ENABLED"):
        monkeypatch.delenv(key, raising=False)

    settings = ProcessSettings.for_role("toolbox")

    assert settings.environment == "debug"
    assert str(settings.configuration_directory) == "config"
    assert settings.guardrail_enabled is False
