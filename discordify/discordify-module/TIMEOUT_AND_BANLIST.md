# Timeout and Banlist (Discordify Spaces Module)

## Timeout (server-enforced)

The server rejects events from users who are currently timed out in the space. Timeout state is stored in the **space room** and applies to the space and all its child rooms.

### State event (frontend-readable)

- **Event type:** `com.Discordify.Spaces_Module.timeout`
- **State key:** Matrix user ID of the timed-out user (e.g. `@user:example.com`)
- **Content:**
  ```json
  {
    "expires_ts": 1234567890123,
    "duration_seconds": 600,
    "reason": "optional reason"
  }
  ```
  - `expires_ts`: Unix timestamp in **milliseconds** when the timeout ends. Frontends can use this to show "timed out until …" or a countdown.
  - `duration_seconds`: Original timeout duration in seconds (so the frontend can show "timed out for X minutes").
  - `reason`: Optional string; can be shown to the user.

To timeout a user, a moderator (or user with sufficient power level) sends this state event in the **space** room with `state_key` = the user's Matrix ID. To remove a timeout early, delete the state event or send an updated event with empty content.

---

## Banlist (moderators and above)

The banlist is stored as a single state event in the **space** room. Only moderators and above should have power to send it (enforced by the room’s power levels). When the banlist is updated, the module applies bans/unbans to the space and all its child rooms.

### State event format

- **Event type:** `com.Discordify.Spaces_Module.banlist`
- **State key:** `""` (empty)
- **Content:**
  ```json
  {
    "space_name": "My Server",
    "entries": [
      {
        "user_id": "@banned_user:example.com",
        "reason": "optional reason",
        "banned_at_ts": 1234567890123
      }
    ]
  }
  ```
  - `space_name`: Display name of the space (used in exports so other servers can label imported lists).
  - `entries`: Array of banned users. Each entry has `user_id`, optional `reason`, and `banned_at_ts` (milliseconds).

Moderators can add users (append to `entries` and send the new state event), remove users (remove from `entries` and send the new state event), or manage the list in a Space settings UI. The module reacts to changes by banning/unbanning in the space and all children.

### Export format

Frontends can export the banlist by reading the state event and writing JSON in this shape (so other servers can import it):

```json
{
  "space_name": "Exported Server Name",
  "exported_at_ts": 1234567890123,
  "entries": [
    {
      "user_id": "@user:example.com",
      "reason": "reason",
      "banned_at_ts": 1234567890123
    }
  ]
}
```

- `space_name`: From the banlist state event (or from `m.room.name` of the space).
- `exported_at_ts`: Unix time in milliseconds when the export was generated.
- `entries`: Copy of the `entries` array from the state event.

### Import

To import a banlist (from the same or another server), the frontend (or a bot) should:

1. Parse the exported JSON.
2. Optionally merge with the current banlist (read current state event, merge `entries`, deduplicate by `user_id`).
3. Send a new state event `com.Discordify.Spaces_Module.banlist` with `state_key` `""` and content `{ "space_name": "<local space name>", "entries": [ ... ] }`.

The module will then apply bans for newly added user IDs and unbans for removed user IDs in the space and all child rooms.

### E2EE note

The banlist state event is stored in the space room. If the space room is encrypted (`m.room.encryption`), the event is encrypted like other room state; only members with the room key (e.g. moderators and above) can read it. The server must be able to apply bans, so when the module runs it uses the decrypted state; in an E2EE room only the server (with access to room keys for processing) can see the list for enforcement. Access control (who can edit the list) is enforced by the room’s power levels (moderators and above).
