/*
Copyright 2024 New Vector Ltd.
SPDX-License-Identifier: AGPL-3.0-only OR GPL-3.0-only OR LicenseRef-Element-Commercial
*/

import React, { useCallback, useMemo } from "react";
import { RoomEvent } from "matrix-js-sdk/src/matrix";
import {
    ArrowLeftIcon,
    EndCallIcon,
    MicOffSolidIcon,
    MicOnSolidIcon,
    ShareScreenSolidIcon,
} from "@vector-im/compound-design-tokens/assets/web/icons";

import defaultDispatcher from "../../dispatcher/dispatcher";
import { Action } from "../../dispatcher/actions";
import { type ViewRoomPayload } from "../../dispatcher/payloads/ViewRoomPayload";
import { CallStore, CallStoreEvent } from "../../stores/CallStore";
import { SdkContextClass } from "../../contexts/SDKContext";
import { UPDATE_EVENT } from "../../stores/AsyncStore";
import { useEventEmitterState } from "../../hooks/useEventEmitter";
import { _t } from "../../languageHandler";
import MatrixClientPeg from "../../MatrixClientPeg";
import Toolbar from "../../accessibility/Toolbar";
import { RovingAccessibleButton } from "../../accessibility/RovingTabIndex";
import { type ButtonEvent } from "../views/elements/AccessibleButton";

/**
 * Discord-style persistent bar at the bottom when the user is in a call
 * but viewing another room. Provides: jump back to call, mute self, mute all,
 * end call, screenshare (open call to manage).
 */
export const PersistentCallBar: React.FC = () => {
    const roomViewStore = SdkContextClass.instance.roomViewStore;

    const connectedCalls = useEventEmitterState(
        CallStore.instance,
        CallStoreEvent.ConnectedCalls,
        () => Array.from(CallStore.instance.connectedCalls),
    );

    const { roomId: currentRoomId, viewingCall } = useEventEmitterState(
        roomViewStore,
        UPDATE_EVENT,
        () => ({
            roomId: roomViewStore.getRoomId(),
            viewingCall: roomViewStore.isViewingCall(),
        }),
    );

    const callToShow = useMemo(() => {
        if (connectedCalls.length === 0) return null;
        const first = connectedCalls[0];
        if (currentRoomId === first.roomId && viewingCall) return null;
        return first;
    }, [connectedCalls, currentRoomId, viewingCall]);

    const room = callToShow
        ? MatrixClientPeg.get()?.getRoom(callToShow.roomId)
        : null;
    const roomName = useEventEmitterState(
        room ?? undefined,
        RoomEvent.Name,
        () => room?.name ?? callToShow?.roomId ?? "",
    );

    const onJumpBack = useCallback(
        (ev: ButtonEvent) => {
            ev.preventDefault();
            ev.stopPropagation();
            if (!callToShow) return;
            defaultDispatcher.dispatch<ViewRoomPayload>({
                action: Action.ViewRoom,
                room_id: callToShow.roomId,
                view_call: true,
                metricsTrigger: "PersistentCallBar",
            });
        },
        [callToShow],
    );

    const onEndCall = useCallback(
        (ev: ButtonEvent) => {
            ev.preventDefault();
            ev.stopPropagation();
            if (!callToShow) return;
            callToShow.disconnect().catch((e) => console.error("Failed to leave call", e));
        },
        [callToShow],
    );

    if (!callToShow) return null;

    return (
        <div className="mx_PersistentCallBar" role="region" aria-label={_t("voip|persistent_call_bar")}>
            <Toolbar className="mx_PersistentCallBar_toolbar">
                <RovingAccessibleButton
                    onClick={onJumpBack}
                    className="mx_PersistentCallBar_button mx_PersistentCallBar_jumpBack"
                    title={_t("voip|jump_back_to_call")}
                    aria-label={_t("voip|jump_back_to_call")}
                >
                    <ArrowLeftIcon className="mx_Icon mx_Icon_16" />
                    <span className="mx_PersistentCallBar_roomName">{roomName || _t("voip|voice_channel")}</span>
                </RovingAccessibleButton>
                <div className="mx_PersistentCallBar_actions">
                    <RovingAccessibleButton
                        onClick={onJumpBack}
                        className="mx_PersistentCallBar_button mx_PersistentCallBar_iconButton"
                        title={_t("voip|mute_self_hint")}
                        aria-label={_t("voip|mute_self_hint")}
                    >
                        <MicOnSolidIcon className="mx_Icon mx_Icon_20" />
                    </RovingAccessibleButton>
                    <RovingAccessibleButton
                        onClick={onJumpBack}
                        className="mx_PersistentCallBar_button mx_PersistentCallBar_iconButton"
                        title={_t("voip|mute_all_hint")}
                        aria-label={_t("voip|mute_all_hint")}
                    >
                        <MicOffSolidIcon className="mx_Icon mx_Icon_20" />
                    </RovingAccessibleButton>
                    <RovingAccessibleButton
                        onClick={onJumpBack}
                        className="mx_PersistentCallBar_button mx_PersistentCallBar_iconButton"
                        title={_t("voip|screenshare_manage_hint")}
                        aria-label={_t("voip|screenshare_manage_hint")}
                    >
                        <ShareScreenSolidIcon className="mx_Icon mx_Icon_20" />
                    </RovingAccessibleButton>
                    <RovingAccessibleButton
                        onClick={onEndCall}
                        className="mx_PersistentCallBar_button mx_PersistentCallBar_iconButton mx_PersistentCallBar_endCall"
                        title={_t("action|leave")}
                        aria-label={_t("action|leave")}
                    >
                        <EndCallIcon className="mx_Icon mx_Icon_24" />
                    </RovingAccessibleButton>
                </div>
            </Toolbar>
        </div>
    );
};
