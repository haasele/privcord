/*
 * Create new Matrix server (enterprise-matrix-stack). Collects wizard fields and POSTs to server_creation_api_url.
 */

import React, { useState } from "react";
import { _t } from "../../../languageHandler";
import Modal from "../../../Modal";
import BaseDialog from "./BaseDialog";
import Field from "../elements/Field";
import SdkConfig from "../../../SdkConfig";

const STEPS = ["server_and_space", "federation", "secrets"] as const;
type Step = (typeof STEPS)[number];

export interface CreateServerPayload {
    server_handle: string;
    domain: string;
    space_name: string;
    space_description: string;
    federation_mode: "private" | "public";
    federation_port?: number;
    federation_whitelist?: string[];
    passwords: {
        postgres_main: string;
        postgres_media: string;
        redis?: string;
        registration_shared_secret: string;
        turn_shared_secret: string;
        livekit_api_key: string;
        livekit_api_secret: string;
    };
    postgres_federated_enabled?: boolean;
}

interface IProps {
    onFinished(ok: boolean): void;
}

export const CreateServerDialog: React.FC<IProps> = ({ onFinished }) => {
    const apiBase = SdkConfig.get().server_creation_api_url?.replace(/\/$/, "");
    const [stepIndex, setStepIndex] = useState(0);
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [result, setResult] = useState<{ job_id?: string; namespace?: string; status?: string } | null>(null);

    const [serverHandle, setServerHandle] = useState("");
    const [domain, setDomain] = useState("");
    const [spaceName, setSpaceName] = useState("");
    const [spaceDescription, setSpaceDescription] = useState("");
    const [federationMode, setFederationMode] = useState<"private" | "public">("private");
    const [federationPort, setFederationPort] = useState("8448");
    const [federationWhitelist, setFederationWhitelist] = useState("");
    const [postgresMain, setPostgresMain] = useState("");
    const [postgresMedia, setPostgresMedia] = useState("");
    const [redisPassword, setRedisPassword] = useState("");
    const [registrationSecret, setRegistrationSecret] = useState("");
    const [turnSecret, setTurnSecret] = useState("");
    const [livekitKey, setLivekitKey] = useState("");
    const [livekitSecret, setLivekitSecret] = useState("");
    const [postgresFederated, setPostgresFederated] = useState(false);

    const step = STEPS[stepIndex];
    const isLastStep = stepIndex === STEPS.length - 1;

    const buildPayload = (): CreateServerPayload => ({
        server_handle: serverHandle.trim().toLowerCase().replace(/\s+/g, "-"),
        domain: domain.trim(),
        space_name: spaceName.trim(),
        space_description: spaceDescription.trim(),
        federation_mode: federationMode,
        federation_port: federationMode === "public" ? parseInt(federationPort, 10) || 8448 : undefined,
        federation_whitelist:
            federationMode === "public" && federationWhitelist.trim()
                ? federationWhitelist.split(/[\s,]+/).map((s) => s.trim()).filter(Boolean)
                : undefined,
        passwords: {
            postgres_main: postgresMain,
            postgres_media: postgresMedia,
            redis: redisPassword || undefined,
            registration_shared_secret: registrationSecret,
            turn_shared_secret: turnSecret,
            livekit_api_key: livekitKey,
            livekit_api_secret: livekitSecret,
        },
        postgres_federated_enabled: postgresFederated,
    });

    const onSubmit = async (): Promise<void> => {
        if (!apiBase) {
            setError(_t("create_server|no_api_configured"));
            return;
        }
        setBusy(true);
        setError(null);
        try {
            const res = await fetch(`${apiBase}/api/v1/servers`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(buildPayload()),
            });
            const data = await res.json().catch(() => ({}));
            if (!res.ok) {
                throw new Error(data?.error ?? data?.message ?? res.statusText);
            }
            setResult({
                job_id: data.job_id,
                namespace: data.namespace,
                status: data.status ?? "creating",
            });
        } catch (e: any) {
            setError(e?.message ?? _t("common|error"));
        } finally {
            setBusy(false);
        }
    };

    if (result) {
        return (
            <BaseDialog
                title={_t("create_server|result_title")}
                onFinished={() => onFinished(true)}
                contentId="mx_CreateServerDialog_result"
            >
                <div className="mx_Dialog_content">
                    <p>{_t("create_server|result_message")}</p>
                    {result.namespace && (
                        <p>
                            <strong>{_t("create_server|namespace")}:</strong> {result.namespace}
                        </p>
                    )}
                    {result.job_id && (
                        <p>
                            <strong>{_t("create_server|job_id")}:</strong> {result.job_id}
                        </p>
                    )}
                    <p>{_t("create_server|result_hint")}</p>
                </div>
                <div className="mx_Dialog_buttons">
                    <button className="mx_Dialog_primary" onClick={() => onFinished(true)}>
                        {_t("action|ok")}
                    </button>
                </div>
            </BaseDialog>
        );
    }

    return (
        <BaseDialog
            title={_t("create_server|title")}
            onFinished={() => onFinished(false)}
            contentId="mx_CreateServerDialog"
            fixedWidth={true}
        >
            <div className="mx_Dialog_content">
                {step === "server_and_space" && (
                    <>
                        <Field
                            label={_t("create_server|server_handle")}
                            type="text"
                            value={serverHandle}
                            onChange={(e) => setServerHandle(e.target.value)}
                            placeholder="mycompany"
                        />
                        <Field
                            label={_t("create_server|domain")}
                            type="text"
                            value={domain}
                            onChange={(e) => setDomain(e.target.value)}
                            placeholder="matrix.example.com"
                        />
                        <Field
                            label={_t("create_server|space_name")}
                            type="text"
                            value={spaceName}
                            onChange={(e) => setSpaceName(e.target.value)}
                            placeholder="My Company Chat"
                        />
                        <Field
                            label={_t("create_server|space_description")}
                            type="text"
                            value={spaceDescription}
                            onChange={(e) => setSpaceDescription(e.target.value)}
                            placeholder="Official company Matrix space."
                        />
                    </>
                )}
                {step === "federation" && (
                    <>
                        <Field
                            label={_t("create_server|federation_mode")}
                            element="select"
                            value={federationMode}
                            onChange={(e) => setFederationMode(e.target.value as "private" | "public")}
                        >
                            <option value="private">{_t("create_server|federation_private")}</option>
                            <option value="public">{_t("create_server|federation_public")}</option>
                        </Field>
                        {federationMode === "public" && (
                            <>
                                <Field
                                    label={_t("create_server|federation_port")}
                                    type="text"
                                    value={federationPort}
                                    onChange={(e) => setFederationPort(e.target.value)}
                                />
                                <Field
                                    label={_t("create_server|federation_whitelist")}
                                    type="text"
                                    value={federationWhitelist}
                                    onChange={(e) => setFederationWhitelist(e.target.value)}
                                    placeholder="other.example.com, another.example.com"
                                />
                            </>
                        )}
                    </>
                )}
                {step === "secrets" && (
                    <>
                        <Field
                            label={_t("create_server|postgres_main")}
                            type="password"
                            value={postgresMain}
                            onChange={(e) => setPostgresMain(e.target.value)}
                        />
                        <Field
                            label={_t("create_server|postgres_media")}
                            type="password"
                            value={postgresMedia}
                            onChange={(e) => setPostgresMedia(e.target.value)}
                        />
                        <Field
                            label={_t("create_server|redis_password")}
                            type="password"
                            value={redisPassword}
                            onChange={(e) => setRedisPassword(e.target.value)}
                        />
                        <Field
                            label={_t("create_server|registration_shared_secret")}
                            type="password"
                            value={registrationSecret}
                            onChange={(e) => setRegistrationSecret(e.target.value)}
                        />
                        <Field
                            label={_t("create_server|turn_shared_secret")}
                            type="password"
                            value={turnSecret}
                            onChange={(e) => setTurnSecret(e.target.value)}
                        />
                        <Field
                            label={_t("create_server|livekit_api_key")}
                            type="text"
                            value={livekitKey}
                            onChange={(e) => setLivekitKey(e.target.value)}
                        />
                        <Field
                            label={_t("create_server|livekit_api_secret")}
                            type="password"
                            value={livekitSecret}
                            onChange={(e) => setLivekitSecret(e.target.value)}
                        />
                        <label className="mx_CreateServerDialog_checkbox">
                            <input
                                type="checkbox"
                                checked={postgresFederated}
                                onChange={(e) => setPostgresFederated(e.target.checked)}
                            />
                            {_t("create_server|postgres_federated_enabled")}
                        </label>
                    </>
                )}
                {error && <div className="mx_CreateServerDialog_error text-danger">{error}</div>}
            </div>
            <div className="mx_Dialog_buttons">
                {stepIndex > 0 ? (
                    <button onClick={() => setStepIndex(stepIndex - 1)}>{_t("action|back")}</button>
                ) : (
                    <button onClick={() => onFinished(false)}>{_t("action|cancel")}</button>
                )}
                {isLastStep ? (
                    <button className="mx_Dialog_primary" onClick={onSubmit} disabled={busy}>
                        {busy ? _t("common|loading") : _t("create_server|submit")}
                    </button>
                ) : (
                    <button className="mx_Dialog_primary" onClick={() => setStepIndex(stepIndex + 1)}>
                        {_t("action|next")}
                    </button>
                )}
            </div>
        </BaseDialog>
    );
};

export const showCreateServerDialog = (onFinished?: (ok: boolean) => void): void => {
    Modal.createDialog(
        CreateServerDialog,
        { onFinished: onFinished ?? (() => {}) },
        "mx_CreateServerDialog",
    );
};
