"""
Unit tests for DiscordifySpacesModule.check_event_allowed (timeout logic).
"""
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from discordify_module.module import DiscordifySpacesModule
from discordify_module.module import DiscordifySpacesConfig


@pytest.fixture
def minimal_config():
    return DiscordifySpacesConfig(
        channels=[{"name": "general", "type": "text"}],
        voice_room_type="org.matrix.msc3401.video_room",
        join_rule="public",
        history_visibility="shared",
        encryption=False,
        admin_power_level=100,
        restrict_to_local_users=False,
        max_concurrency=1,
        retry_count=1,
        space_name="",
        space_avatar="",
        roles=[],
    )


@pytest.fixture
def mock_api():
    api = MagicMock()
    api.server_name = "test.server"
    return api


@pytest.mark.asyncio
async def test_check_event_allowed_no_sender(minimal_config, mock_api):
    """Event with no sender is allowed."""
    module = DiscordifySpacesModule(minimal_config, mock_api)
    event = MagicMock(spec=[])
    event.sender = None
    event.room_id = "!room:test"
    allowed, _ = await module.check_event_allowed(event, None)
    assert allowed is True


@pytest.mark.asyncio
async def test_check_event_allowed_no_timeout_state(minimal_config, mock_api):
    """No timeout state for user -> allow."""
    mock_api.get_state_event = AsyncMock(return_value=None)
    module = DiscordifySpacesModule(minimal_config, mock_api)
    event = MagicMock()
    event.sender = "@user:test.server"
    event.room_id = "!room:test"
    allowed, _ = await module.check_event_allowed(event, None)
    assert allowed is True
    mock_api.get_state_event.assert_called_once()


@pytest.mark.asyncio
async def test_check_event_allowed_timeout_expired(minimal_config, mock_api):
    """Timeout state with expires_ts in the past -> allow."""
    mock_api.get_state_event = AsyncMock(return_value=MagicMock(
        content={"expires_ts": 1},
    ))
    module = DiscordifySpacesModule(minimal_config, mock_api)
    event = MagicMock()
    event.sender = "@user:test.server"
    event.room_id = "!room:test"
    allowed, _ = await module.check_event_allowed(event, None)
    assert allowed is True


@pytest.mark.asyncio
async def test_check_event_allowed_timeout_not_expired(minimal_config, mock_api):
    """Timeout state with expires_ts in the future -> reject."""
    now_ms = int(time.time() * 1000)
    future = now_ms + 60000
    mock_api.get_state_event = AsyncMock(return_value=MagicMock(
        content={"expires_ts": future},
    ))
    module = DiscordifySpacesModule(minimal_config, mock_api)
    event = MagicMock()
    event.sender = "@user:test.server"
    event.room_id = "!room:test"
    allowed, _ = await module.check_event_allowed(event, None)
    assert allowed is False


@pytest.mark.asyncio
async def test_check_event_allowed_uses_space_from_parent(minimal_config, mock_api):
    """When state_events has m.space.parent, timeout is checked in parent space."""
    mock_api.get_state_event = AsyncMock(return_value=None)
    module = DiscordifySpacesModule(minimal_config, mock_api)
    event = MagicMock()
    event.sender = "@user:test.server"
    event.room_id = "!child:test"
    state_events = [("m.space.parent", "!space:test")]
    await module.check_event_allowed(event, state_events)
    mock_api.get_state_event.assert_called_once()
    call_args = mock_api.get_state_event.call_args
    assert call_args[0][0] == "!space:test"
