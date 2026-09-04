"""验证配置默认值和保持安全边界的功能开关。"""

from opspilot.config.settings import Settings


def test_enhancements_default_to_disabled() -> None:
    settings = Settings(_env_file=None)

    assert settings.skills_enabled is False
    assert settings.superset_mcp_enabled is False
    assert settings.specialists_enabled is False
    assert settings.model_inference_concurrency == 1


def test_no_secret_is_required_for_process_startup() -> None:
    settings = Settings(_env_file=None)

    assert settings.deepseek_api_key is None
    assert settings.database_url is None
