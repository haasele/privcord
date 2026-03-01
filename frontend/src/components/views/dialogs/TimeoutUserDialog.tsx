/*
 * Timeout user in server (Discordify). Sends com.Discordify.Spaces_Module.timeout state in parent space.
 */

import React, { useState } from "react";
import { type Room } from "matrix-js-sdk/src/matrix";
import { _t } from "../../../languageHandler";
import Modal from "../../../Modal";
import BaseDialog from "./BaseDialog";
import Field from "../elements/Field";
import { setSpaceTimeout } from "../../../utils/discordify";
import MatrixClientContext from "../../../contexts/MatrixClientContext";

const DURATIONS = [
    { label: "1 minute", seconds: 60 },
    { label: "5 minutes", seconds: 300 },
    { label: "10 minutes", seconds: 600 },
    { label: "1 hour", seconds: 3600 },
    { label: "1 day", seconds: 86400 },
];

interface IProps {
    space: Room;
    userId: string;
    userDisplayName?: string;
    onFinished(ok: boolean): void;
}

export const TimeoutUserDialog: React.FC<IProps> = ({ space, userId, userDisplayName, onFinished }) => {
    const client = React.useContext(MatrixClientContext);
    const [durationSeconds, setDurationSeconds] = useState(600);
    const [reason, setReason] = useState("");
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const onTimeout = async (): Promise<void> => {
        setBusy(true);
        setError(null);
        try {
            const expires_ts = Date.now() + durationSeconds * 1000;
            await setSpaceTimeout(client, space.roomId, userId, {
                expires_ts,
                duration_seconds: durationSeconds,
                reason: reason.trim() || undefined,
            });
            onFinished(true);
        } catch (e: any) {
            setError(e?.message ?? _t("common|error"));
        } finally {
            setBusy(false);
        }
    };

    const displayName = userDisplayName || userId;

    return (
        <BaseDialog
            title={_t("discordify|timeout_user_title", { name: displayName })}
            onFinished={() => onFinished(false)}
            contentId="mx_TimeoutUserDialog"
        >
            <div className="mx_Dialog_content">
                <p>{_t("discordify|timeout_user_description", { name: displayName })}</p>
                <Field
                    label={_t("discordify|duration")}
                    element="select"
                    value={String(durationSeconds)}
                    onChange={(ev) => setDurationSeconds(Number(ev.target.value))}
                >
                    {DURATIONS.map((d) => (
                        <option key={d.seconds} value={d.seconds}>
                            {d.label}
                        </option>
                    ))}
                </Field>
                <Field
                    label={_t("discordify|reason_optional")}
                    type="text"
                    value={reason}
                    onChange={(ev) => setReason(ev.target.value)}
                />
                {error && <div className="mx_TimeoutUserDialog_error text-danger">{error}</div>}
            </div>
            <div className="mx_Dialog_buttons">
                <button className="mx_Dialog_primary" onClick={onTimeout} disabled={busy}>
                    {busy ? _t("common|loading") : _t("discordify|timeout_action")}
                </button>
                <button onClick={() => onFinished(false)}>{_t("action|cancel")}</button>
            </div>
        </BaseDialog>
    );
};

export const showTimeoutUserDialog = (
    space: Room,
    userId: string,
    userDisplayName?: string,
    onFinished?: (ok: boolean) => void,
): void => {
    Modal.createDialog(
        TimeoutUserDialog,
        { space, userId, userDisplayName, onFinished: onFinished ?? (() => {}) },
        "mx_TimeoutUserDialog",
    );
};
