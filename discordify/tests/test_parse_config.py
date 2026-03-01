"""
Unit tests for DiscordifySpacesModule.parse_config.
"""
import pytest
from synapse.module_api.errors import ConfigError

from discordify_module.module import DiscordifySpacesModule


def test_parse_config_minimal_valid():
    """Valid minimal config with one text channel."""
    config = {
        "channels": [{"name": "general", "type": "text"}],
    }
    parsed = DiscordifySpacesModule.parse_config(config)
    assert len(parsed.channels) == 1
    assert parsed.channels[0]["name"] == "general"
    assert parsed.channels[0]["type"] == "text"
    assert parsed.voice_room_type == "org.matrix.msc3401.video_room"
    assert parsed.join_rule == "public"
    assert parsed.history_visibility == "shared"
    assert parsed.encryption is False
    assert parsed.admin_power_level == 100
    assert parsed.roles == []


def test_parse_config_channels_empty_fails():
    """Empty channels list raises ConfigError."""
    with pytest.raises(ConfigError, match="nicht-leere Liste"):
        DiscordifySpacesModule.parse_config({"channels": []})


def test_parse_config_channels_missing_fails():
    """Missing channels raises ConfigError."""
    with pytest.raises(ConfigError, match="nicht-leere Liste"):
        DiscordifySpacesModule.parse_config({})


def test_parse_config_channels_not_list_fails():
    """channels not a list raises ConfigError."""
    with pytest.raises(ConfigError, match="nicht-leere Liste"):
        DiscordifySpacesModule.parse_config({"channels": "general"})


def test_parse_config_channel_type_invalid_fails():
    """Invalid channel type raises ConfigError."""
    with pytest.raises(ConfigError, match="text.*voice"):
        DiscordifySpacesModule.parse_config({
            "channels": [{"name": "general", "type": "invalid"}],
        })


def test_parse_config_channel_missing_name_fails():
    """Channel without name raises ConfigError."""
    with pytest.raises(ConfigError, match="name"):
        DiscordifySpacesModule.parse_config({
            "channels": [{"type": "text"}],
        })


def test_parse_config_voice_and_text():
    """Config with voice and text channels and optional fields."""
    config = {
        "channels": [
            {"name": "general", "type": "text", "default": True},
            {"name": "Voice", "type": "voice", "topic": "Chat"},
        ],
        "voice_room_type": "org.matrix.msc3401.video_room",
        "space_name": "My Server",
        "roles": [{"name": "Admin", "power_level": 100}],
    }
    parsed = DiscordifySpacesModule.parse_config(config)
    assert len(parsed.channels) == 2
    assert parsed.channels[0]["name"] == "general"
    assert parsed.channels[0].get("default") is True
    assert parsed.channels[1]["type"] == "voice"
    assert parsed.channels[1].get("topic") == "Chat"
    assert parsed.space_name == "My Server"
    assert len(parsed.roles) == 1
    assert parsed.roles[0]["name"] == "Admin"
    assert parsed.roles[0]["power_level"] == 100


def test_parse_config_roles_invalid_fails():
    """Roles must be a list of dicts with name."""
    with pytest.raises(ConfigError, match="Rolle"):
        DiscordifySpacesModule.parse_config({
            "channels": [{"name": "g", "type": "text"}],
            "roles": [{"power_level": 50}],
        })
