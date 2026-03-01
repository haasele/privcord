/*
 * Space (server) settings: Discordify banlist. View, add, remove, export, import.
 */

import React, { useCallback, useEffect, useState } from "react";
import { type Room, type MatrixClient } from "matrix-js-sdk/src/matrix";
import { CloseIcon } from "@vector-im/compound-design-tokens/assets/web/icons";

import { _t } from "../../../languageHandler";
import AccessibleButton from "../elements/AccessibleButton";
import Field from "../elements/Field";
import SettingsTab from "../settings/tabs/SettingsTab";
import { SettingsSection } from "../settings/shared/SettingsSection";
import {
    canSendDiscordifyModerationInSpace,
    getSpaceBanlist,
    removeFromSpaceBanlist,
    addToSpaceBanlist,
    type BanlistEntry,
    type BanlistContent,
} from "../../../utils/discordify";
import { formatRelativeTime } from "../../../DateUtils";

interface IProps {
    matrixClient: MatrixClient;
    space: Room;
}

const EXPORT_MIME = "application/json";

export const SpaceSettingsModerationTab: React.FC<IProps> = ({ matrixClient: cli, space }) => {
    const [banlist, setBanlist] = useState<BanlistContent | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [addUserId, setAddUserId] = useState("");
    const [addReason, setAddReason] = useState("");
    const [addBusy, setAddBusy] = useState(false);
    const [importBusy, setImportBusy] = useState(false);

    const canModerate = canSendDiscordifyModerationInSpace(cli, space);

    const loadBanlist = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const data = await getSpaceBanlist(cli, space.roomId);
            setBanlist(data);
        } catch (e: any) {
            setError(e?.message ?? _t("common|error"));
        } finally {
            setLoading(false);
        }
    }, [cli, space.roomId]);

    useEffect(() => {
        loadBanlist();
    }, [loadBanlist]);

    const onRemove = async (userId: string): Promise<void> => {
        setError(null);
        try {
            await removeFromSpaceBanlist(cli, space, userId);
            await loadBanlist();
        } catch (e: any) {
            setError(e?.message ?? _t("common|error"));
        }
    };

    const onAdd = async (): Promise<void> => {
        const uid = addUserId.trim();
        if (!uid) return;
        setAddBusy(true);
        setError(null);
        try {
            await addToSpaceBanlist(cli, space, uid, addReason.trim() || undefined);
            setAddUserId("");
            setAddReason("");
            await loadBanlist();
        } catch (e: any) {
            setError(e?.message ?? _t("common|error"));
        } finally {
            setAddBusy(false);
        }
    };

    const onExport = (): void => {
        if (!banlist) return;
        const payload = {
            space_name: banlist.space_name,
            exported_at_ts: Date.now(),
            entries: banlist.entries,
        };
        const blob = new Blob([JSON.stringify(payload, null, 2)], { type: EXPORT_MIME });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `banlist-${space.roomId.replace(/[^a-zA-Z0-9-_]/g, "_")}-${Date.now()}.json`;
        a.click();
        URL.revokeObjectURL(url);
    };

    const onImport = async (ev: React.ChangeEvent<HTMLInputElement>): Promise<void> => {
        const file = ev.target.files?.[0];
        if (!file) return;
        setImportBusy(true);
        setError(null);
        try {
            const text = await file.text();
            const data = JSON.parse(text) as { space_name?: string; entries?: BanlistEntry[] };
            const entries = Array.isArray(data.entries) ? data.entries : [];
            const current = await getSpaceBanlist(cli, space.roomId);
            const existingIds = new Set((current?.entries ?? []).map((e) => e.user_id));
            const toAdd = entries.filter((e) => e.user_id && !existingIds.has(e.user_id));
            for (const entry of toAdd) {
                await addToSpaceBanlist(cli, space, entry.user_id, entry.reason);
                existingIds.add(entry.user_id);
            }
            await loadBanlist();
        } catch (e: any) {
            setError(e?.message ?? _t("common|error"));
        } finally {
            setImportBusy(false);
            ev.target.value = "";
        }
    };

    if (!canModerate) {
        return (
            <SettingsTab>
                <SettingsSection heading={_t("discordify|moderation_tab_title")}>
                    <p className="mx_SpaceSettingsModerationTab_noPermission">
                        {_t("discordify|moderation_tab_no_permission")}
                    </p>
                </SettingsSection>
            </SettingsTab>
        );
    }

    const entries = banlist?.entries ?? [];

    return (
        <SettingsTab>
            <SettingsSection heading={_t("discordify|ban_list_heading")}>
                {error && <div className="mx_SpaceSettingsModerationTab_error text-danger">{error}</div>}
                {loading ? (
                    <p>{_t("common|loading")}</p>
                ) : (
                    <>
                        <div className="mx_SpaceSettingsModerationTab_actions">
                            <AccessibleButton kind="primary" onClick={onExport} disabled={entries.length === 0}>
                                {_t("action|export")}
                            </AccessibleButton>
                            <label className="mx_SpaceSettingsModerationTab_importLabel">
                                <input
                                    type="file"
                                    accept={EXPORT_MIME}
                                    onChange={onImport}
                                    disabled={importBusy}
                                    style={{ display: "none" }}
                                />
                                <AccessibleButton kind="secondary" disabled={importBusy} element="span">
                                    {importBusy ? _t("common|loading") : _t("action|import")}
                                </AccessibleButton>
                            </label>
                        </div>
                        <ul className="mx_SpaceSettingsModerationTab_list">
                            {entries.length === 0 ? (
                                <li className="mx_SpaceSettingsModerationTab_empty">{_t("discordify|ban_list_empty")}</li>
                            ) : (
                                entries.map((entry) => (
                                    <li key={entry.user_id} className="mx_SpaceSettingsModerationTab_entry">
                                        <span className="mx_SpaceSettingsModerationTab_entryUserId">{entry.user_id}</span>
                                        {entry.reason && (
                                            <span className="mx_SpaceSettingsModerationTab_entryReason">
                                                {entry.reason}
                                            </span>
                                        )}
                                        <span className="mx_SpaceSettingsModerationTab_entryDate">
                                            {formatRelativeTime(new Date(entry.banned_at_ts))}
                                        </span>
                                        <AccessibleButton
                                            kind="danger"
                                            onClick={() => onRemove(entry.user_id)}
                                            className="mx_SpaceSettingsModerationTab_remove"
                                            aria-label={_t("discordify|unban")}
                                        >
                                            <CloseIcon />
                                        </AccessibleButton>
                                    </li>
                                ))
                            )}
                        </ul>
                    </>
                )}
            </SettingsSection>
            <SettingsSection heading={_t("discordify|add_ban_heading")}>
                <div className="mx_SpaceSettingsModerationTab_add">
                    <Field
                        label={_t("discordify|user_id_label")}
                        type="text"
                        value={addUserId}
                        onChange={(ev) => setAddUserId(ev.target.value)}
                        placeholder="@user:server.example.com"
                    />
                    <Field
                        label={_t("discordify|reason_optional")}
                        type="text"
                        value={addReason}
                        onChange={(ev) => setAddReason(ev.target.value)}
                    />
                    <AccessibleButton kind="primary" onClick={onAdd} disabled={addBusy || !addUserId.trim()}>
                        {addBusy ? _t("common|loading") : _t("action|ban")}
                    </AccessibleButton>
                </div>
            </SettingsSection>
        </SettingsTab>
    );
};
