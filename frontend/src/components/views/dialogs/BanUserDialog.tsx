/*
 * Ban user from server (Discordify banlist). Sends com.Discordify.Spaces_Module.banlist state in parent space.
 */

import React, { useState } from "react";
import { type Room } from "matrix-js-sdk/src/matrix";
import { _t } from "../../../languageHandler";
import Modal from "../../../Modal";
import BaseDialog from "./BaseDialog";
import Field from "../elements/Field";
import { addToSpaceBanlist } from "../../../utils/discordify";
import MatrixClientContext from "../../../contexts/MatrixClientContext";

interface IProps {
    space: Room;
    userId: string;
    userDisplayName?: string;
    onFinished(ok: boolean): void;
}

export const BanUserDialog: React.FC<IProps> = ({ space, userId, userDisplayName, onFinished }) => {
    const client = React.useContext(MatrixClientContext);
    const [reason, setReason] = useState("");
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const onBan = async (): Promise<void> => {
        setBusy(true);
        setError(null);
        try {
            await addToSpaceBanlist(client, space, userId, reason.trim() || undefined);
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
            title={_t("discordify|ban_user_title", { name: displayName })}
            onFinished={() => onFinished(false)}
            contentId="mx_BanUserDialog"
        >
            <div className="mx_Dialog_content">
                <p>{_t("discordify|ban_user_description", { name: displayName, serverName: space.name ?? "" })}</p>
                <Field
                    label={_t("discordify|reason_optional")}
                    type="text"
                    value={reason}
                    onChange={(ev) => setReason(ev.target.value)}
                    className="mx_BanUserDialog_reason"
                />
                {error && <div className="mx_BanUserDialog_error text-danger">{error}</div>}
            </div>
            <div className="mx_Dialog_buttons">
                <button className="mx_Dialog_primary" onClick={onBan} disabled={busy}>
                    {busy ? _t("common|loading") : _t("action|ban")}
                </button>
                <button onClick={() => onFinished(false)}>{_t("action|cancel")}</button>
            </div>
        </BaseDialog>
    );
};

export const showBanUserDialog = (
    space: Room,
    userId: string,
    userDisplayName?: string,
    onFinished?: (ok: boolean) => void,
): void => {
    Modal.createDialog(
        BanUserDialog,
        { space, userId, userDisplayName, onFinished: onFinished ?? (() => {}) },
        "mx_BanUserDialog",
    );
};
