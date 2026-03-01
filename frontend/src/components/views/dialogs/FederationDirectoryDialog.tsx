/*
 * Show list of servers from the Federation Directory (GET /api/v1/servers).
 */

import React, { useEffect, useState } from "react";
import { _t } from "../../../languageHandler";
import Modal from "../../../Modal";
import BaseDialog from "./BaseDialog";
import SdkConfig from "../../../SdkConfig";
import { LinkIcon } from "@vector-im/compound-design-tokens/assets/web/icons";

export interface DirectoryServer {
    server_name: string;
    base_url: string;
    handle?: string;
    federation_port?: number;
    registered_at?: string;
    updated_at?: string;
}

interface IProps {
    onFinished(): void;
}

export const FederationDirectoryDialog: React.FC<IProps> = ({ onFinished }) => {
    const directoryUrl = SdkConfig.get().federation_directory_url?.replace(/\/$/, "");
    const [servers, setServers] = useState<DirectoryServer[]>([]);
    const [loading, setLoading] = useState(!!directoryUrl);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        if (!directoryUrl) {
            setError(_t("federation_directory|no_url_configured"));
            setLoading(false);
            return;
        }
        let cancelled = false;
        setError(null);
        fetch(`${directoryUrl}/api/v1/servers`)
            .then((res) => {
                if (!res.ok) throw new Error(res.statusText);
                return res.json();
            })
            .then((data) => {
                if (cancelled) return;
                const list = Array.isArray(data.servers) ? data.servers : [];
                setServers(list);
            })
            .catch((e: Error) => {
                if (!cancelled) setError(e?.message ?? _t("common|error"));
            })
            .finally(() => {
                if (!cancelled) setLoading(false);
            });
        return () => {
            cancelled = true;
        };
    }, [directoryUrl]);

    return (
        <BaseDialog
            title={_t("federation_directory|title")}
            onFinished={onFinished}
            contentId="mx_FederationDirectoryDialog"
            fixedWidth={true}
        >
            <div className="mx_Dialog_content mx_FederationDirectoryDialog_content">
                {loading && <p>{_t("common|loading")}</p>}
                {error && <div className="mx_FederationDirectoryDialog_error text-danger">{error}</div>}
                {!loading && !error && (
                    <>
                        <p className="mx_FederationDirectoryDialog_intro">{_t("federation_directory|intro")}</p>
                        {servers.length === 0 ? (
                            <p className="mx_FederationDirectoryDialog_empty">{_t("federation_directory|empty")}</p>
                        ) : (
                            <ul className="mx_FederationDirectoryDialog_list">
                                {servers.map((s) => (
                                    <li key={s.server_name} className="mx_FederationDirectoryDialog_item">
                                        <span className="mx_FederationDirectoryDialog_itemName">
                                            {s.handle || s.server_name}
                                        </span>
                                        <span className="mx_FederationDirectoryDialog_itemServer">
                                            {s.server_name}
                                        </span>
                                        <a
                                            href={s.base_url}
                                            target="_blank"
                                            rel="noreferrer noopener"
                                            className="mx_FederationDirectoryDialog_itemLink"
                                            aria-label={_t("federation_directory|open_server", {
                                                name: s.server_name,
                                            })}
                                        >
                                            <LinkIcon />
                                        </a>
                                    </li>
                                ))}
                            </ul>
                        )}
                    </>
                )}
            </div>
        </BaseDialog>
    );
};

export const showFederationDirectoryDialog = (onFinished?: () => void): void => {
    Modal.createDialog(
        FederationDirectoryDialog,
        { onFinished: onFinished ?? (() => {}) },
        "mx_FederationDirectoryDialog",
    );
};
