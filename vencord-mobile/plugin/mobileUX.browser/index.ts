/*
 * Vencord, a Discord client mod
 * Copyright (c) 2026 ArielNya
 * SPDX-License-Identifier: GPL-3.0-or-later
 */

import definePlugin from "@utils/types";

// M0 skeleton: proves the userplugin ships in browser.js. Features land in M3+ (see PLAN.md §4).
export default definePlugin({
    name: "MobileUX",
    description: "Touch-friendly behaviour for Vencord on Android (Vendroid)",
    authors: [{ name: "ArielNya", id: 0n }]
});
