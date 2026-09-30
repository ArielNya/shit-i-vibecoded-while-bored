/*
 * Vencord, a Discord client mod
 * Copyright (c) 2026 Ariel and contributors
 * SPDX-License-Identifier: GPL-3.0-or-later
 */

import { definePluginSettings } from "@api/Settings";
import { IS_MOBILE } from "@utils/constants";
import definePlugin, { OptionType } from "@utils/types";
import { ContextMenuApi, FluxDispatcher } from "@webpack/common";

const ROOT_CLASSES = [
    "mux-mobile",
    "mux-desktop",
    "mux-density-comfortable",
    "mux-density-compact",
    "mux-font-small",
    "mux-font-medium",
    "mux-font-large",
    "mux-sidebar-open"
] as const;

const openSidebar = () => document.documentElement.classList.add("mux-sidebar-open");
const closeSidebar = () => document.documentElement.classList.remove("mux-sidebar-open");
const isActive = () => settings.store.activation === "on" || (settings.store.activation === "auto" && IS_MOBILE);

let holdTimer: ReturnType<typeof setTimeout> | undefined;
let holdStart: { x: number; y: number; target: EventTarget | null; } | undefined;
let originalBackPress: (() => boolean) | undefined;

function cancelLongPress() {
    clearTimeout(holdTimer);
    holdTimer = undefined;
    holdStart = undefined;
}

function applyThemeState() {
    const root = document.documentElement;
    root.classList.remove(...ROOT_CLASSES);

    const active = isActive();

    root.classList.add(active ? "mux-mobile" : "mux-desktop");
    if (!active) return;

    root.classList.add(`mux-density-${settings.store.density}`);
    root.classList.add(`mux-font-${settings.store.fontSize}`);
}

const settings = definePluginSettings({
    activation: {
        type: OptionType.SELECT,
        description: "Enable mobile UX automatically on mobile, force it for desktop testing, or disable it",
        options: [
            { label: "Auto (mobile only)", value: "auto", default: true },
            { label: "Always on (testing)", value: "on" },
            { label: "Off", value: "off" }
        ],
        onChange: applyThemeState
    },
    density: {
        type: OptionType.SELECT,
        description: "Vertical spacing used by messages and lists",
        options: [
            { label: "Comfortable", value: "comfortable", default: true },
            { label: "Compact", value: "compact" }
        ],
        onChange: applyThemeState
    },
    fontSize: {
        type: OptionType.SELECT,
        description: "Base text size for the mobile layout",
        options: [
            { label: "Small", value: "small" },
            { label: "Medium", value: "medium", default: true },
            { label: "Large", value: "large" }
        ],
        onChange: applyThemeState
    },
    longPressMenus: {
        type: OptionType.BOOLEAN,
        description: "Open message actions when holding a message",
        default: true
    },
    backStack: {
        type: OptionType.BOOLEAN,
        description: "Close an open context menu before the Android back action",
        default: true
    }
});

export default definePlugin({
    name: "MobileUX",
    description: "Browser-only behavior and theme controls for a touch-friendly VendroidEnhanced layout",
    authors: [{ name: "Ariel", id: 0n }],
    tags: ["Appearance", "Accessibility"],
    settings,

    patches: [
        {
            find: "Message must not be a thread starter message",
            replacement: {
                match: /onContextMenu:(\i),onKeyDown:(\i),onClick:(\i),compact:(\i),contentOnly:/,
                replace: "onContextMenu:$1,onTouchStartCapture:e=>$self.startLongPress(e),onTouchMoveCapture:e=>$self.moveLongPress(e),onTouchEndCapture:$self.cancelLongPress,onTouchCancelCapture:$self.cancelLongPress,onKeyDown:$2,onClick:$3,compact:$4,contentOnly:"
            }
        },
        {
            find: /onContextMenu:\i=>\i\?\.\(\i,\i\),onMouseEnter:/,
            replacement: {
                match: /(?<=onContextMenu:\i=>\i\?\.\(\i,\i\),)(?=onMouseEnter:)/,
                replace: "onTouchStartCapture:e=>$self.startLongPress(e),onTouchMoveCapture:e=>$self.moveLongPress(e),onTouchEndCapture:$self.cancelLongPress,onTouchCancelCapture:$self.cancelLongPress,"
            }
        }
    ],

    startLongPress(event: React.TouchEvent<HTMLElement>) {
        if (!isActive() || !settings.store.longPressMenus || event.touches.length !== 1) return;
        cancelLongPress();
        const touch = event.touches[0];
        holdStart = { x: touch.clientX, y: touch.clientY, target: event.target };
        holdTimer = setTimeout(() => {
            const start = holdStart;
            cancelLongPress();
            start?.target?.dispatchEvent(new MouseEvent("contextmenu", {
                bubbles: true,
                cancelable: true,
                clientX: start.x,
                clientY: start.y,
                button: 2,
                buttons: 2
            }));
        }, 550);
    },

    moveLongPress(event: React.TouchEvent<HTMLElement>) {
        const touch = event.touches[0];
        if (!touch || !holdStart || Math.hypot(touch.clientX - holdStart.x, touch.clientY - holdStart.y) > 12) cancelLongPress();
    },

    cancelLongPress,

    start() {
        applyThemeState();
        FluxDispatcher.subscribe("MOBILE_WEB_SIDEBAR_OPEN", openSidebar);
        FluxDispatcher.subscribe("MOBILE_WEB_SIDEBAR_CLOSE", closeSidebar);
        const mobile = window.VencordMobile;
        if (mobile?.onBackPress) {
            originalBackPress = mobile.onBackPress;
            mobile.onBackPress = () => {
                if (isActive() && settings.store.backStack && document.querySelector('[role="menu"]')) {
                    ContextMenuApi.closeContextMenu();
                    return true;
                }
                return originalBackPress?.() ?? false;
            };
        }
    },

    stop() {
        FluxDispatcher.unsubscribe("MOBILE_WEB_SIDEBAR_OPEN", openSidebar);
        FluxDispatcher.unsubscribe("MOBILE_WEB_SIDEBAR_CLOSE", closeSidebar);
        cancelLongPress();
        if (originalBackPress && window.VencordMobile) window.VencordMobile.onBackPress = originalBackPress;
        originalBackPress = undefined;
        document.documentElement.classList.remove(...ROOT_CLASSES);
    }
});
