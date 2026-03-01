import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from synapse.module_api import ModuleApi
from synapse.module_api.errors import ConfigError

logger = logging.getLogger(__name__)

INITIALIZED_EVENT_TYPE = "com.Discordify.Spaces_Module.initialized"
TIMEOUT_EVENT_TYPE = "com.Discordify.Spaces_Module.timeout"
BANLIST_EVENT_TYPE = "com.Discordify.Spaces_Module.banlist"


@dataclass
class DiscordifySpacesConfig:
    channels: List[Dict[str, Any]]
    voice_room_type: str
    join_rule: str
    history_visibility: str
    encryption: bool
    admin_power_level: int
    restrict_to_local_users: bool
    max_concurrency: int
    retry_count: int
    space_name: str
    space_avatar: str
    roles: List[Dict[str, Any]]


class DiscordifySpacesModule:
    def __init__(self, config: DiscordifySpacesConfig, api: ModuleApi):
        self.config = config
        self.api = api
        self.server_name = api.server_name
        self._semaphore = asyncio.Semaphore(config.max_concurrency)

        self.api.register_third_party_rules_callbacks(
            on_new_event=self.on_new_event,
            check_event_allowed=self.check_event_allowed,
        )

    @staticmethod
    def parse_config(config: Dict[str, Any]) -> DiscordifySpacesConfig:
        channels = config.get("channels")
        if not isinstance(channels, list) or not channels:
            raise ConfigError("'channels' muss eine nicht-leere Liste sein.")

        parsed_channels = []
        for i, chan in enumerate(channels):
            if not isinstance(chan, dict):
                raise ConfigError("Jeder Kanal muss ein Dictionary sein.")
            if chan.get("type") not in ("text", "voice"):
                raise ConfigError("Kanaltyp muss 'text' oder 'voice' sein.")
            if not isinstance(chan.get("name"), str):
                raise ConfigError("Kanal benötigt String 'name'.")
            ch_out = {"name": chan["name"], "type": chan["type"], "order": i, "nsfw": False, "default": False}
            if isinstance(chan.get("topic"), str):
                ch_out["topic"] = chan["topic"]
            if "join_rule" in chan:
                ch_out["join_rule"] = chan["join_rule"]
            if "history_visibility" in chan:
                ch_out["history_visibility"] = chan["history_visibility"]
            if "encryption" in chan:
                ch_out["encryption"] = bool(chan["encryption"])
            if chan.get("nsfw"):
                ch_out["nsfw"] = True
            if chan.get("default"):
                ch_out["default"] = True
            if "order" in chan:
                ch_out["order"] = int(chan["order"])
            if isinstance(chan.get("category"), str):
                ch_out["category"] = chan["category"]
            parsed_channels.append(ch_out)

        roles_raw = config.get("roles") or []
        if not isinstance(roles_raw, list):
            raise ConfigError("'roles' muss eine Liste sein.")
        parsed_roles = []
        for r in roles_raw:
            if not isinstance(r, dict):
                raise ConfigError("Jede Rolle muss ein Dictionary sein.")
            name = r.get("name")
            if not isinstance(name, str):
                raise ConfigError("Rolle benötigt String 'name'.")
            parsed_roles.append({
                "name": name,
                "power_level": int(r.get("power_level", 0)),
            })

        return DiscordifySpacesConfig(
            channels=parsed_channels,
            voice_room_type=config.get(
                "voice_room_type", "org.matrix.msc3401.video_room"
            ),
            join_rule=config.get("join_rule", "public"),
            history_visibility=config.get("history_visibility", "shared"),
            encryption=config.get("encryption", False),
            admin_power_level=int(config.get("admin_power_level", 100)),
            restrict_to_local_users=bool(config.get("restrict_to_local_users", False)),
            max_concurrency=int(config.get("max_concurrency", 4)),
            retry_count=int(config.get("retry_count", 3)),
            space_name=config.get("space_name") or "",
            space_avatar=config.get("space_avatar") or "",
            roles=parsed_roles,
        )

    async def on_new_event(self, event: Any, state_events: Any) -> None:
        """Called after an event is persisted. Initialize space when m.room.create has type m.space; apply banlist changes."""
        room_id = getattr(event, "room_id", None)
        if not room_id:
            return
        content = getattr(event, "content", None) or {}

        # Banlist updated: apply bans/unbans to space and all children
        if event.type == BANLIST_EVENT_TYPE and getattr(event, "state_key", "") == "":
            await self._apply_banlist_changes(room_id, event, state_events)
            return

        if event.type != "m.room.create":
            return
        if content.get("type") != "m.space":
            return

        creator = event.sender

        if self.config.restrict_to_local_users:
            if not creator.endswith(f":{self.server_name}"):
                return

        # Idempotenz prüfen
        existing = await self.api.get_state_event(
            room_id, INITIALIZED_EVENT_TYPE, ""
        )
        if existing:
            return

        logger.info("Initialisiere Space %s", room_id)

        asyncio.create_task(self._initialize_space(room_id, creator))

    async def check_event_allowed(
        self, event: Any, state_events: Any
    ) -> Tuple[bool, Optional[dict]]:
        """Reject events from users who are currently timed out in this space."""
        sender = getattr(event, "sender", None)
        if not sender:
            return True, None
        room_id = getattr(event, "room_id", None)
        if not room_id:
            return True, None
        space_id = room_id
        if state_events:
            for key in state_events:
                if isinstance(key, (list, tuple)) and len(key) >= 2 and key[0] == "m.space.parent":
                    space_id = key[1]
                    break
        timeout_state = await self.api.get_state_event(
            space_id, TIMEOUT_EVENT_TYPE, sender
        )
        if not timeout_state or not getattr(timeout_state, "content", None):
            return True, None
        content = timeout_state.content
        expires_ts = content.get("expires_ts") or 0
        now_ms = int(time.time() * 1000)
        if now_ms < expires_ts:
            return False, None
        return True, None

    async def _apply_banlist_changes(
        self, space_id: str, event: Any, state_events: Any
    ) -> None:
        """When banlist state is updated, ban/unban users in the space and all child rooms."""
        try:
            new_entries = (event.content or {}).get("entries", [])
            prev = getattr(event, "unsigned", None) or {}
            old_entries = (prev.get("prev_content") or {}).get("entries", [])
            old_user_ids = {e.get("user_id") for e in old_entries if e.get("user_id")}
            new_user_ids = {e.get("user_id") for e in new_entries if e.get("user_id")}
            added = new_user_ids - old_user_ids
            removed = old_user_ids - new_user_ids
            child_ids = []
            if state_events:
                for key in state_events:
                    if isinstance(key, (list, tuple)) and len(key) >= 2 and key[0] == "m.space.child":
                        child_ids.append(key[1])
            rooms_to_update = [space_id] + child_ids
            for user_id in added:
                entry = next((e for e in new_entries if e.get("user_id") == user_id), {})
                reason = entry.get("reason", "")
                for rid in rooms_to_update:
                    try:
                        await self.api.send_state_event(
                            room_id=rid,
                            event_type="m.room.member",
                            state_key=user_id,
                            content={"membership": "ban", "reason": reason},
                        )
                    except Exception:
                        logger.warning("Failed to ban %s in %s: %s", user_id, rid)
            for user_id in removed:
                for rid in rooms_to_update:
                    try:
                        await self.api.send_state_event(
                            room_id=rid,
                            event_type="m.room.member",
                            state_key=user_id,
                            content={"membership": "leave"},
                        )
                    except Exception:
                        logger.warning("Failed to unban %s in %s: %s", user_id, rid)
        except Exception:
            logger.exception("Failed to apply banlist changes in %s", space_id)

    async def _initialize_space(self, space_id: str, creator: str):
        try:
            created: List[Optional[str]] = []
            for ch in self.config.channels:
                room_id = await self._create_channel_with_retry(space_id, creator, ch)
                created.append(room_id)

            if self.config.space_name:
                await self.api.send_state_event(
                    room_id=space_id,
                    event_type="m.room.name",
                    state_key="",
                    content={"name": self.config.space_name},
                )
            if self.config.space_avatar:
                await self.api.send_state_event(
                    room_id=space_id,
                    event_type="m.room.avatar",
                    state_key="",
                    content={"url": self.config.space_avatar},
                )
            if self.config.roles:
                await self.api.send_state_event(
                    room_id=space_id,
                    event_type="com.Discordify.Spaces_Module.roles",
                    state_key="",
                    content={"roles": self.config.roles},
                )
            default_room_id = None
            for i, ch in enumerate(self.config.channels):
                if i < len(created) and created[i] and ch.get("default"):
                    default_room_id = created[i]
                    break
            if default_room_id is None:
                for i, ch in enumerate(self.config.channels):
                    if i < len(created) and created[i] and ch.get("type") == "text":
                        default_room_id = created[i]
                        break
            if default_room_id:
                await self.api.send_state_event(
                    room_id=space_id,
                    event_type="com.Discordify.Spaces_Module.default_channel",
                    state_key="",
                    content={"room_id": default_room_id},
                )

            await self.api.send_state_event(
                room_id=space_id,
                event_type=INITIALIZED_EVENT_TYPE,
                state_key="",
                content={"initialized": True},
            )

        except Exception:
            logger.exception("Fehler bei Space-Initialisierung %s", space_id)

    async def _create_channel_with_retry(
        self, space_id: str, creator: str, channel: Dict[str, Any]
    ) -> Optional[str]:
        for attempt in range(self.config.retry_count):
            try:
                async with self._semaphore:
                    return await self._create_single_channel(space_id, creator, channel)
            except Exception:
                if attempt == self.config.retry_count - 1:
                    logger.exception(
                        "Kanal %s endgültig fehlgeschlagen", channel["name"]
                    )
                    return None
                else:
                    await asyncio.sleep(2 ** attempt)
        return None

    async def _create_single_channel(
        self, space_id: str, creator: str, channel: Dict[str, Any]
    ) -> str:
        name = channel["name"]
        ctype = channel["type"]
        join_rule = channel.get("join_rule", self.config.join_rule)
        history_visibility = channel.get("history_visibility", self.config.history_visibility)
        encryption = channel.get("encryption", self.config.encryption)

        initial_state = [
            {
                "type": "m.room.join_rules",
                "state_key": "",
                "content": {"join_rule": join_rule},
            },
            {
                "type": "m.room.history_visibility",
                "state_key": "",
                "content": {"history_visibility": history_visibility},
            },
        ]

        if encryption:
            initial_state.append(
                {
                    "type": "m.room.encryption",
                    "state_key": "",
                    "content": {"algorithm": "m.megolm.v1.aes-sha2"},
                }
            )

        if channel.get("topic"):
            initial_state.append(
                {
                    "type": "m.room.topic",
                    "state_key": "",
                    "content": {"topic": channel["topic"]},
                }
            )

        if ctype == "voice":
            initial_state.append(
                {
                    "type": "m.room.type",
                    "state_key": "",
                    "content": {"type": self.config.voice_room_type},
                }
            )

        new_room_id = await self.api.create_room(
            creator=creator,
            name=name,
            initial_state=initial_state,
        )

        child_content: Dict[str, Any] = {"via": [self.server_name], "order": str(channel.get("order", 0))}
        if channel.get("category"):
            child_content["category"] = channel["category"]

        await self.api.send_state_event(
            room_id=space_id,
            event_type="m.space.child",
            state_key=new_room_id,
            content=child_content,
        )

        if channel.get("nsfw"):
            await self.api.send_state_event(
                room_id=new_room_id,
                event_type="com.Discordify.Spaces_Module.nsfw",
                state_key="",
                content={"nsfw": True},
            )

        await self.api.send_state_event(
            room_id=new_room_id,
            event_type="m.space.parent",
            state_key=space_id,
            content={"via": [self.server_name], "canonical": True},
        )

        await self._ensure_admin_power(new_room_id, creator)
        return new_room_id

    async def _ensure_admin_power(self, room_id: str, creator: str):
        current_pl = await self.api.get_state_event(
            room_id, "m.room.power_levels", ""
        )

        if not current_pl:
            return

        content = dict(current_pl.content)
        users = dict(content.get("users", {}))
        current_level = users.get(creator, 0)

        if current_level < self.config.admin_power_level:
            users[creator] = self.config.admin_power_level
            content["users"] = users

            await self.api.send_state_event(
                room_id=room_id,
                event_type="m.room.power_levels",
                state_key="",
                content=content,
            )
