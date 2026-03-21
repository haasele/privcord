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

    async def _get_state_event(self, room_id: str, event_type: str, state_key: str) -> Optional[Any]:
        try:
            events = await self.api.get_state_events_in_room(room_id, [(event_type, state_key)])
            for ev in events:
                if ev.type == event_type and ev.state_key == state_key:
                    return ev
        except Exception:
            pass
        return None

    async def _send_state_event(self, room_id: str, sender: str, event_type: str, state_key: str, content: dict) -> None:
        await self.api.create_and_send_event_into_room({
            "type": event_type,
            "room_id": room_id,
            "sender": sender,
            "state_key": state_key,
            "content": content,
        })

    async def on_new_event(self, event: Any, state_events: Any) -> None:
        room_id = getattr(event, "room_id", None)
        if not room_id:
            return
        content = getattr(event, "content", None) or {}

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

        existing = await self._get_state_event(room_id, INITIALIZED_EVENT_TYPE, "")
        if existing:
            return

        logger.info("Initialisiere Space %s", room_id)
        from twisted.internet import defer, reactor
        defer.ensureDeferred(self._initialize_space(room_id, creator))

    async def check_event_allowed(
        self, event: Any, state_events: Any
    ) -> Tuple[bool, Optional[dict]]:
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
        timeout_ev = await self._get_state_event(space_id, TIMEOUT_EVENT_TYPE, sender)
        if not timeout_ev:
            return True, None
        tc = getattr(timeout_ev, "content", {}) or {}
        expires_ts = tc.get("expires_ts") or 0
        now_ms = int(time.time() * 1000)
        if now_ms < expires_ts:
            return False, None
        return True, None

    async def _apply_banlist_changes(
        self, space_id: str, event: Any, state_events: Any
    ) -> None:
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
                        await self.api.update_room_membership(
                            sender=event.sender,
                            target=user_id,
                            room_id=rid,
                            new_membership="ban",
                            content={"reason": reason},
                        )
                    except Exception:
                        logger.warning("Failed to ban %s in %s", user_id, rid)
            for user_id in removed:
                for rid in rooms_to_update:
                    try:
                        await self.api.update_room_membership(
                            sender=event.sender,
                            target=user_id,
                            room_id=rid,
                            new_membership="leave",
                        )
                    except Exception:
                        logger.warning("Failed to unban %s in %s", user_id, rid)
        except Exception:
            logger.exception("Failed to apply banlist changes in %s", space_id)

    async def _initialize_space(self, space_id: str, creator: str):
        try:
            created: List[Optional[str]] = []
            for ch in self.config.channels:
                room_id = await self._create_channel_with_retry(space_id, creator, ch)
                created.append(room_id)

            if self.config.space_name:
                await self._send_state_event(space_id, creator, "m.room.name", "", {"name": self.config.space_name})
            if self.config.space_avatar:
                await self._send_state_event(space_id, creator, "m.room.avatar", "", {"url": self.config.space_avatar})
            if self.config.roles:
                await self._send_state_event(space_id, creator, "com.Discordify.Spaces_Module.roles", "", {"roles": self.config.roles})

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
                await self._send_state_event(space_id, creator, "com.Discordify.Spaces_Module.default_channel", "", {"room_id": default_room_id})

            await self._send_state_event(space_id, creator, INITIALIZED_EVENT_TYPE, "", {"initialized": True})
            logger.info("Space %s initialisiert mit %d Kanälen", space_id, len([c for c in created if c]))

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
            {"type": "m.room.join_rules", "state_key": "", "content": {"join_rule": join_rule}},
            {"type": "m.room.history_visibility", "state_key": "", "content": {"history_visibility": history_visibility}},
        ]

        if encryption:
            initial_state.append({"type": "m.room.encryption", "state_key": "", "content": {"algorithm": "m.megolm.v1.aes-sha2"}})

        if channel.get("topic"):
            initial_state.append({"type": "m.room.topic", "state_key": "", "content": {"topic": channel["topic"]}})

        if ctype == "voice":
            initial_state.append({"type": "m.room.type", "state_key": "", "content": {"type": self.config.voice_room_type}})

        room_config = {
            "name": name,
            "preset": "public_chat",
            "initial_state": initial_state,
        }

        result = await self.api.create_room(user_id=creator, config=room_config)
        new_room_id = result[0]

        child_content: Dict[str, Any] = {"via": [self.server_name], "order": str(channel.get("order", 0))}
        if channel.get("category"):
            child_content["category"] = channel["category"]

        await self._send_state_event(space_id, creator, "m.space.child", new_room_id, child_content)

        if channel.get("nsfw"):
            await self._send_state_event(new_room_id, creator, "com.Discordify.Spaces_Module.nsfw", "", {"nsfw": True})

        await self._send_state_event(new_room_id, creator, "m.space.parent", space_id, {"via": [self.server_name], "canonical": True})

        await self._ensure_admin_power(new_room_id, creator)
        return new_room_id

    async def _ensure_admin_power(self, room_id: str, creator: str):
        pl_event = await self._get_state_event(room_id, "m.room.power_levels", "")
        if not pl_event:
            return

        content = dict(getattr(pl_event, "content", {}) or {})
        users = dict(content.get("users", {}))
        current_level = users.get(creator, 0)

        if current_level < self.config.admin_power_level:
            users[creator] = self.config.admin_power_level
            content["users"] = users
            await self._send_state_event(room_id, creator, "m.room.power_levels", "", content)
