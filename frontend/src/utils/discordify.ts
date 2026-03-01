/*
 * Discordify module (Synapse) integration: timeout and banlist state events.
 * See discordify-module/TIMEOUT_AND_BANLIST.md and module.py.
 */

import type { MatrixClient, Room } from "matrix-js-sdk/src/matrix";

export const DISCORDIFY_TIMEOUT_EVENT_TYPE = "com.Discordify.Spaces_Module.timeout";
export const DISCORDIFY_BANLIST_EVENT_TYPE = "com.Discordify.Spaces_Module.banlist";

/** Minimum power level in the space to act as "moderator" (send timeout/banlist). */
export const DISCORDIFY_MODERATOR_POWER_LEVEL = 50;

export interface TimeoutContent {
    expires_ts: number;
    duration_seconds: number;
    reason?: string;
}

export interface BanlistEntry {
    user_id: string;
    reason?: string;
    banned_at_ts: number;
}

export interface BanlistContent {
    space_name: string;
    entries: BanlistEntry[];
}

/**
 * Check if the current user can send Discordify moderation state events in the given space.
 */
export function canSendDiscordifyModerationInSpace(client: MatrixClient, space: Room): boolean {
    const userId = client.getSafeUserId();
    const pl = space.currentState.getMember(userId)?.powerLevel ?? 0;
    return pl >= DISCORDIFY_MODERATOR_POWER_LEVEL;
}

/**
 * Send timeout state event in the space. Pass empty content to clear timeout.
 */
export async function setSpaceTimeout(
    client: MatrixClient,
    spaceId: string,
    userId: string,
    content: TimeoutContent | Record<string, never>,
): Promise<void> {
    await client.sendStateEvent(spaceId, DISCORDIFY_TIMEOUT_EVENT_TYPE, content, userId);
}

/**
 * Read current banlist from space state.
 */
export async function getSpaceBanlist(
    client: MatrixClient,
    spaceId: string,
): Promise<BanlistContent | null> {
    const ev = await client.getStateEvent(spaceId, DISCORDIFY_BANLIST_EVENT_TYPE, "");
    if (!ev || typeof ev !== "object") return null;
    const entries = Array.isArray((ev as BanlistContent).entries) ? (ev as BanlistContent).entries : [];
    return {
        space_name: (ev as BanlistContent).space_name ?? "",
        entries,
    };
}

/**
 * Write banlist state event to the space.
 */
export async function setSpaceBanlist(
    client: MatrixClient,
    spaceId: string,
    content: BanlistContent,
): Promise<void> {
    await client.sendStateEvent(spaceId, DISCORDIFY_BANLIST_EVENT_TYPE, content, "");
}

/**
 * Add a user to the space banlist (read current, append, send).
 */
export async function addToSpaceBanlist(
    client: MatrixClient,
    space: Room,
    userId: string,
    reason?: string,
): Promise<void> {
    const current = await getSpaceBanlist(client, space.roomId);
    const spaceName = space.name ?? current?.space_name ?? "";
    const entries = current?.entries ?? [];
    if (entries.some((e) => e.user_id === userId)) return;
    const newEntry: BanlistEntry = {
        user_id: userId,
        reason: reason ?? undefined,
        banned_at_ts: Date.now(),
    };
    await setSpaceBanlist(client, space.roomId, {
        space_name: spaceName,
        entries: [...entries, newEntry],
    });
}

/**
 * Remove a user from the space banlist.
 */
export async function removeFromSpaceBanlist(
    client: MatrixClient,
    space: Room,
    userId: string,
): Promise<void> {
    const current = await getSpaceBanlist(client, space.roomId);
    if (!current) return;
    const entries = current.entries.filter((e) => e.user_id !== userId);
    await setSpaceBanlist(client, space.roomId, {
        space_name: current.space_name,
        entries,
    });
}
