# vencord-mobile — plan

A mobile-UX project for **Vencord running inside Vendroid** on Android. It has
two parts: a **theme** that works on stock Vendroid today, and a **plugin**
(plus a small Vendroid fork) for the behaviour CSS can't fix. The goal is to
make Discord-in-Vendroid feel like a phone app rather than a desktop site
squeezed onto a phone.

## Status

| Milestone | State |
| --- | --- |
| M0 | Done except one check: skeleton, subtree fork of Vendroid (`vendroid/`, upstream `006ca4d`, unmodified), plugin skeleton, `scripts/build-vencord.sh`. The build couldn't be run in the session that wrote it, because `codeload.github.com` (needed by Vencord's `gifenc` git dependency) was blocked. Run it once to tick M0 |
| M1 | Theme §3 items 1–6 written, linted, tested in headless Chromium (applies on an emulated phone, no effect on desktop, every rule block parses). Not yet checked against live Discord on a device |

Selectors that need a device check during M2, because they come from Discord's
DOM, which the theme was written without seeing: the hover-bar reveal on
focus (§3.2), the `channels___` / `guildsnav___` list ids, and `[class*="member_"]`.

---

## 0. Sources and sourcing rule

Everything below is based only on these sources, pinned so the plan can be
checked again later:

| Source | What it is | Pinned at |
| --- | --- | --- |
| [Vencord Docs](https://docs.vencord.dev) — read from its source repo [`Vencord/Docs`](https://github.com/Vencord/Docs) | Official plugin-dev documentation | `0f98bda` (2026-09-23) |
| [`Vencord/Vendroid`](https://github.com/Vencord/Vendroid) README + source | Official Android client. It has no docs site, so the README and its ~400 lines of source are its documentation | `006ca4d` (2025-08-31) |
| [`Vendicated/Vencord`](https://github.com/Vendicated/Vencord) `CONTRIBUTING.md`, build scripts, typings | Official rules and build behaviour that the docs point to | `7f0c10c` (2026-09-29) |

The network sandbox this plan was written in blocks `docs.vencord.dev`, so
the docs were read from their Markdown source at the commit above. The
content is the same as the site.

**Third-party docs.** The Vencord docs never mention BetterDiscord.
Vencord's own **Themes** settings tab does: it links the BetterDiscord theme
list and tells users to install `.theme.css` files. Vencord's theme-header
parser (`src/main/themes/index.ts`) is also adapted from BetterDiscord's meta
parser. So the only thing this project takes from BetterDiscord is the
`/** @name … */` theme header format, and it's used as Vencord parses it.
BetterDiscord's docs aren't needed.
The Vendroid README recommends **VendroidEnhanced** (`vendroid.nin0.dev`).
It's cited, but it's out of scope for v1 (see §9).

---

## 1. What the sources establish

### 1.1 How Vendroid works (from its source)

- It's a single `Activity` with one `WebView` that loads `https://discord.com/app`.
  - `minSdk 21`, `targetSdk 33`.
  - JavaScript and DOM storage are on.
  - Only the `INTERNET` permission is requested.
- **It injects the official Vencord build and nothing else.** On every cold
  start, `HttpClient.fetchVencord` downloads
  `github.com/Vendicated/Vencord/releases/download/devbuild/browser.js`
  (`Constants.JS_BUNDLE_URL`).
  - This happens on the **main thread**; StrictMode is loosened with
    `permitNetwork()` to allow it.
  - If the download fails, `onCreate` returns and the app stays blank.
- `browser.js` is the output of `pnpm buildWebStandalone`, which Vencord CI
  uploads to the `devbuild` release (`.github/workflows/build.yml`). In other
  words, Vendroid runs the **web** flavour of Vencord (`IS_WEB`).
- `onPageStarted` runs `browser.js` and then `res/raw/vencord_mobile.js`.
  That file:
  - defines `window.VencordMobile.onBackPress()`. The hardware back button
    calls it, and it tries, in order: close a modal (via the `esc` keybind
    module), close the QuickCSS Monaco window, open the mobile sidebar
    (`MOBILE_WEB_SIDEBAR_OPEN` Flux event). If it returns `false`, Android
    handles the press.
  - tracks sidebar state through the `MOBILE_WEB_SIDEBAR_OPEN` / `_CLOSE`
    Flux events.
  - injects `browser.css`, also hardcoded to the official `devbuild` release.
- The main frame and all `.css` requests are proxied through
  `HttpURLConnection`, with the **`Content-Security-Policy` header stripped**.
- Links that aren't on `discord.com` open in an external app. `discord.com`
  deep links are routed in-app through `NavigationRouter.transitionTo`.
- File uploads go through the system picker (`onShowFileChooser`).
- WebView remote debugging is on **only in debug builds**
  (`setWebContentsDebuggingEnabled(BuildConfig.DEBUG)`).
- JS console output goes to logcat under the tag `Vencord`.
- The activity sets no `windowSoftInputMode` and handles
  `orientation|keyboardHidden|screenSize` config changes itself.
- The README says: the mobile site "has many issues", Vendroid is a
  "proof of concept", and it's "not actively worked on, but not abandoned".

### 1.2 What the Vencord docs and repo give us

- **Plugins** are made with `definePlugin`, and settings with
  `definePluginSettings` (reactive: `settings.store.x`, `settings.use([...])`).
  Private plugins go in `src/userplugins/<camelCaseName>/index.tsx`.
  Rebuild with `pnpm buildWeb` (`--watch`, `--dev`).
- **Plugin APIs that don't need patches** (docs: *Plugin API*):
  - `contextMenus` (by menu ID, e.g. `message`)
  - `chatBarButton`
  - `messagePopoverButton`
  - `onMessageClick`, `onBeforeMessageSend`, `onBeforeMessageEdit`
  - `renderMessageAccessory`, `renderMessageDecoration`,
    `renderMemberListDecorator`
  - `commands`
- **Patches** (docs: *Patches*) are RegExp `find` / `match` / `replace`.
  - Anchor them on Intl keys or non-mangled names, and use `\i` for
    identifiers.
  - Call `$self.method()` instead of putting logic in the replacement string.
  - Wrap components in `ErrorBoundary.wrap`.
  - Prefer a patch that breaks over one that matches the wrong code.
  - Keep regexes cheap; dev builds log how long each patch takes.
- **Native code** (`native.ts`) runs only on Node/Electron. It **doesn't
  exist on Vendroid**, so this project can't use it.
- **Platform targeting** (build scripts): a plugin folder or file name
  suffix controls which builds include it.
  - `.web` is excluded from the Discord desktop build.
  - `.browser` is included only in the web builds (extension, userscript,
    standalone `browser.js`).
  - `.desktop` is excluded from web builds.
  - At runtime, `@utils/constants` exports
    `IS_MOBILE = navigator.userAgent.includes("Mobi")`.
- **Themes on web**:
  - **Online Themes** load from URLs.
  - **Local Themes** are uploaded as `.css` and stored in IndexedDB.
  - **QuickCSS** is stored in IndexedDB and edited in a Monaco popup window.
  - Theme metadata comes from the `/** @name @author @description @version
    @source … */` header.
  - The Themes tab says assets must be hosted on GitHub, GitLab, Codeberg,
    Imgur, Discord or Google Fonts. On Vendroid CSP is stripped anyway, but
    we follow that rule so the theme also works in the browser extension and
    on desktop.
- **Debugging**: React DevTools (Settings › Vencord › *Enable React Developer
  Tools*), the Sources search (`Ctrl+Shift+F`) for strings, Intl hashes and
  CSS classes, and `Vencord.Util.runtimeHashMessageKey`.

### 1.3 Rules that shape the design (`CONTRIBUTING.md`)

- **"No plugins that simply hide or redesign UI elements. This can be done
  with CSS."** So all visual work goes in the **theme**, and the plugin does
  only behaviour.
- **"No raw DOM manipulation. Use proper patches and React."** The plugin
  changes the UI only through the plugin APIs, patches and Flux, never by
  mutating the DOM directly. Listening for events (touch gestures) is the one
  grey area, covered in §4.3.
- Niche plugins aren't accepted upstream, and Vendroid itself is a PoC. So
  v1 is a **userplugin**. It's written to upstream standards so it could be
  proposed later: feature request first, and disclose AI use as the
  contributing guide requires.

---

## 2. The key constraint: delivering to the phone

Stock Vendroid always runs the official `browser.js`. **A userplugin can't
run on stock Vendroid.** There are three delivery paths:

| Path | What the user installs | Covers |
| --- | --- | --- |
| **A. Theme only** | Stock Vendroid, plus our theme URL in *Online Themes* (or an uploaded `.css`) | All visual/layout fixes (§3). No build needed. |
| **B. Custom build + Vendroid fork** | Our fork's APK. It loads our `browser.js` / `browser.css` (official Vencord + `mobileUX` userplugin) from our own GitHub release | Theme + plugin behaviour (§4) + app-shell fixes (§5) |
| **C. Upstream** | Nothing extra, if Vencord accepts the plugin | Unlikely (niche, PoC target). Kept as an option, not a goal |

Path A ships first, so the theme is useful without the fork. Path B is the
full experience.

---

## 3. The theme — `MobileUX.theme.css`

The theme is pure CSS. It works on stock Vendroid (path A) and uses the
Vencord/BetterDiscord header format so it shows up properly in the Themes tab.

Scoping:

- Everything is scoped under a media query:
  `@media (pointer: coarse) and (max-width: 900px)`.
- This means installing it on desktop does nothing.
- The plugin can also force it on or off with a class on `<html>` (§4).

Class names:

- Discord's classes are hashed (`profileButtons__9c3be`), so selectors use
  attribute prefix matches (`[class^="profileButtons_"]`) or ARIA/role
  attributes.
- They never use full hashed names.

What the theme fixes:

1. **Touch targets.**
   - Channel rows, guild icons, member rows, buttons, context-menu items and
     settings switches get a minimum height of about 44–48 px.
   - Spacing between neighbouring tap targets increases.
2. **Hover-only controls.**
   - The message popover (react/reply/more) only appears on hover.
   - The theme makes it reachable for the focused/selected message.
   - The plugin (§4.1) also puts those actions in the long-press menu, so
     nothing relies on hover.
3. **Viewport and keyboard.**
   - Use `dvh`/`svh` instead of `vh` so the chat bar isn't hidden under the
     on-screen keyboard or browser chrome.
   - Keep the composer pinned to the bottom.
4. **Safe areas.** `env(safe-area-inset-*)` padding for notches and gesture
   bars. This depends on the fork's edge-to-edge support (§5); it's harmless
   without it.
5. **Vencord's own UI on a phone.**
   - The Vencord settings pages, plugin cards and plugin settings modals are
     made full-width.
   - The plugin list becomes a single column.
   - Modals become full-screen sheets with a visible close button.
6. **Readability.**
   - Variables for base font size and message density: `--mux-font-scale`,
     `--mux-density`.
   - Users can override them in QuickCSS.
7. **Motion and performance.**
   - `prefers-reduced-motion` support.
   - Optionally turn off heavy blur/backdrop-filter and animated
     backgrounds, which are expensive in low-end WebViews.
8. **Layout polish.**
   - The member list and profile panels become full-width slide-overs
     instead of squeezing the chat.
   - Better text wrapping for embeds and code blocks, with horizontal
     scroll inside code blocks rather than the page.

The theme deliberately does **not** hide features. It resizes and reflows
them. Users who want to hide things can add their own QuickCSS on top.

---

## 4. The plugin — `mobileUX` (userplugin, path B)

Location: `src/userplugins/mobileUX.browser/index.tsx`.

- The `.browser` suffix keeps it out of desktop and Vesktop builds.
- At runtime it also checks `IS_MOBILE`, plus a "force on" setting for
  testing in desktop Chrome with device emulation.
- Every feature has its own boolean in `definePluginSettings`, so users can
  switch off anything that annoys them.

### 4.1 Long-press menus instead of hover (API: `contextMenus`)

- On touch, the long-press menu is the only reliable way to reach message,
  user and channel actions.
- The plugin adds the hover-only popover actions (react, reply, edit, copy
  text, copy link, pin, mark unread) to the `message` context menu, using
  the documented `contextMenus.message(children, props)` API.
- It adds similar shortcuts to the `user-context` / `channel-context` menus.
  Menu IDs are found with the method in the docs: inspect the menu element.
- **Spike first (M2):** confirm that a long press in Android WebView fires
  Discord's context-menu handler.
  - If it doesn't, do it with a **patch**: add an `onLongPress` → open
    context menu handler to the message component, anchored on a stable Intl
    key or non-mangled name, following *Patch Safety*.
  - Don't add a global DOM listener for this.

### 4.2 Back-button stack (extends Vendroid's `onBackPress`)

- Vendroid's back chain only knows about modals, QuickCSS and the sidebar.
- The plugin wraps `window.VencordMobile.onBackPress`, only when it exists,
  so it does nothing elsewhere.
- Before falling back to the original handler, it closes, in order:
  1. popouts (profile, emoji/GIF/sticker picker)
  2. open context menus
  3. the thread / forum side view
  4. the search results panel
  5. the member list
- It closes each of these through Discord's own stores and actions, found
  with React DevTools as the docs describe.
- In the fork (§5), the same chain moves into `vencord_mobile.js` properly.
- Also: from the channel list (sidebar open), back goes to the previous
  channel before the app closes, if the "exit on back" setting is off.

### 4.3 Swipe gestures (Flux, not DOM)

- Swipe right from the left edge opens the sidebar; swipe left closes it.
  This dispatches the same `MOBILE_WEB_SIDEBAR_OPEN` / `_CLOSE` Flux events
  that Vendroid listens to.
- Optional: swipe left on a message to reply, like the official app.
  - This should be a small **patch** on the message row component that adds
    touch handlers through React props, which is what "proper patches and
    React" means.
  - A `document` listener would be the fallback, off by default and marked
    as a userplugin-only compromise.
- Thresholds (edge width, distance, speed) are settings.

### 4.4 Chat bar (API: `chatBarButton`)

- An optional compact "⋯" chat-bar button opens a sheet with the actions
  that don't fit on a narrow bar: upload, GIF, sticker, and Vencord's own
  chat-bar buttons.
- A setting hides the individual buttons behind it. The hiding itself is
  done in the theme; the plugin just toggles a class.
- **Enter key:** by default the soft keyboard's Enter inserts a newline, and
  a dedicated send button sends.
  - Implemented with `onBeforeMessageSend`, or a patch on the textarea key
    handler if that's needed.
  - Setting: "Enter sends" on/off.

### 4.5 Tap behaviour (API: `onMessageClick`)

- **Double-tap a message** to add a user-chosen reaction (default ❤️).
  Setting: off, reply, or react with a chosen emoji.
- Stop accidental jumps: tapping a message shouldn't open the profile unless
  the tap is on the avatar or name.

### 4.6 Theme bridge

- The plugin sets `html.mux-mobile` (and `mux-density-*` / `mux-font-*`
  classes) from its settings.
- This way the theme's variables can be controlled from the plugin settings
  UI instead of editing CSS by hand.
- It's a class toggle on the root element, not general DOM manipulation. If
  review ever objects, the same can be done by inserting a `<style>` through
  Vencord's styles API.

### 4.7 Better QuickCSS editing on mobile

- The Monaco popup window is hard to use on a phone.
- Add a plugin setting page (Vencord settings components) with a plain
  full-screen `<textarea>` editor for QuickCSS.
- It reads and writes through `VencordNative.quickCss.get/set`, which the
  web stub stores in IndexedDB.

### 4.8 Out of scope for the plugin

- Anything a CSS rule can do (that stays in the theme, per the contributing
  rules).
- `native.ts` (no Node on Android).
- Push notifications. The WebView has no background process; see §5 and §9.

---

## 5. Vendroid fork — `vendroid-mux` (path B)

Keep the diff small and easy to review. It only needs to be as smooth as the
theme and plugin assume:

1. **Our own bundle.**
   - Make `JS_BUNDLE_URL` and the `browser.css` URL in `vencord_mobile.js`
     build-time config (`buildConfigField`).
   - They point at our GitHub release, which is built with
     `pnpm buildWebStandalone` from Vencord + our userplugin.
2. **Faster, offline-safe startup** (biggest smoothness win).
   - Fetch the bundle **off the main thread** and remove the
     `permitNetwork()` workaround.
   - **Cache** `browser.js` / `browser.css` on disk and start from the cache
     straight away; refresh it in the background (ETag / `If-Modified-Since`).
   - If there's no network, start from the cache instead of a blank screen.
   - Show a splash until `onPageFinished`, which is partly done today via
     `LoadingTheme` and `setVisibility`.
3. **Keyboard.** `android:windowSoftInputMode="adjustResize"` so the composer
   stays above the IME. This matches the theme's `dvh` work.
4. **Edge-to-edge.** Draw behind the system bars and pass the insets into the
   page, so the theme's `safe-area-inset` padding works. Colour the status
   and nav bars from the current Discord theme.
5. **Back button.** Move the extended back-stack logic from §4.2 into
   `vencord_mobile.js`, so it works even with the plugin off.
6. **Debug builds** keep `setWebContentsDebuggingEnabled`, for
   `chrome://inspect` in development (§6).
7. **Small fixes found while reading the source.**
   - `handleUrl` calls `url.getAuthority().equals(...)`. That throws if the
     authority is null, and it doesn't handle `*.discord.com` links, even
     though the manifest accepts them.
   - `VencordNative.goBack` has a no-op `else` branch.

We don't add any WebView → Java bridges beyond what these items need.
`VencordMobileNative` stays minimal, in line with the docs' "don't export
overly broad APIs" guidance for natives.

---

## 6. Development workflow

1. Set up Vencord from source (docs: *Installing Vencord*): git, Node, pnpm,
   `pnpm install --frozen-lockfile`. Set up VS Code with the recommended
   extensions, including **Vencord Companion** for the `vcPlugin` snippet.
2. Build the plugin in `src/userplugins/mobileUX.browser/`, then run
   `pnpm buildWeb --watch --dev`.
3. **First, iterate on desktop.**
   - Load `dist/extension-chrome.zip` as an unpacked extension (docs: *Web
     Browser* install).
   - Open discord.com in Chrome DevTools device emulation, with touch and a
     "Mobi" user agent, and use the plugin's "force on" setting.
   - This is fast to reload and has full DevTools and React DevTools.
4. **Then test on the device.**
   - Build the standalone bundle with `pnpm buildWebStandalone --dev`.
   - Upload it to a test release and install a **debug** build of the
     Vendroid fork.
   - Debug with `chrome://inspect`.
   - Watch logs with `adb logcat -s Vencord`, since Vendroid sends
     `console.*` there.
5. **Theme loop.**
   - Paste into QuickCSS for live edits.
   - Commit to `vencord-mobile/theme/MobileUX.theme.css`.
   - Point *Online Themes* at the raw GitHub URL for stock-Vendroid testing.
6. **Patch hygiene** (docs: *Patches*). Anchor on Intl keys (`#{intl::…}`)
   or non-mangled names, use `\i`, and route logic through `$self`. Check the
   timing logs in dev builds so patches don't slow down startup on low-end
   phones.

---

## 7. Milestones

Each milestone ends with a manual test pass on a real device (§8).

| # | Deliverable | Done when |
| --- | --- | --- |
| **M0** | Project skeleton: this plan, README, `theme/`, `plugin/` (the userplugin source, copied into `Vencord/src/userplugins` at build time), `vendroid/` (fork notes or patches), a build script that produces `browser.js` + `browser.css` | `pnpm buildWebStandalone` output includes `mobileUX`; stock Vencord behaviour is unchanged |
| **M1** | Theme v1 (§3 items 1–6) | On stock Vendroid with the Online Theme URL: every tap target in chat, sidebar, member list and Vencord settings is ≥ 44 px; the composer is never hidden by the keyboard; Vencord settings are usable one-handed |
| **M2** | Spikes, which decide the approach for M3: long-press in WebView, Flux sidebar events, `VencordMobile.onBackPress` wrapping, Enter-key handling | Each spike is written up in this plan with a yes/no and the chosen mechanism (API, patch or fallback) |
| **M3** | Plugin v1: §4.1 long-press menus, §4.2 back stack, §4.6 theme bridge, settings UI | Every action that used to need hover is reachable by long-press; back closes the topmost layer every time and never exits the app unexpectedly |
| **M4** | Vendroid fork: §5 items 1–4 | Cold start works from cache with no network; a warm start shows the UI noticeably faster than stock (measure time to `onPageFinished` from logcat); the IME never covers the composer |
| **M5** | Plugin v2: §4.3 gestures, §4.4 chat bar and Enter behaviour, §4.5 tap actions, §4.7 mobile QuickCSS editor; theme items 7–8 | All features can be toggled on their own; no console errors from our code during a 10-minute session; patches are guarded by ErrorBoundary / try-catch |
| **M6** | Release: signed fork APK on GitHub Releases, theme raw URL, README install guide for paths A and B | A fresh phone goes from nothing to working in under 5 minutes using only the README |

---

## 8. Test matrix

| Device class | Why |
| --- | --- |
| Low-end, Android 8–10, old System WebView | Patch and regex cost, blur cost, startup time |
| Mid-range Android 13–14, gesture navigation | Edge swipes clashing with system back gestures; safe areas |
| Tablet / foldable, landscape | The `max-width` media query boundary; layout split |
| Desktop Chrome, emulated touch | The dev loop; checks the theme does nothing without `pointer: coarse` |

Things to check each time:

- Send, edit, reply and react
- Upload a file
- Voice channel: join/leave only. Voice quality in WebView is out of scope.
- Open a profile
- Go through settings
- Use the back button from every layer
- Rotate the device
- Kill the app and cold-start it offline

---

## 9. Risks and open questions

- **Discord web changes.** Minified class and module changes will break
  selectors and patches.
  - Theme: use prefix and attribute selectors.
  - Plugin: follow *Patch Safety* (failing is better than matching the wrong
    code).
  - Re-test after every Discord web update we notice.
- **Vendroid is a PoC upstream.** Our fork is effectively a new app to
  maintain. We keep the diff small so upstream fixes merge in easily.
- **Long-press behaviour in WebView** is unconfirmed until M2. §4.1 has a
  patch fallback.
- **System gesture conflicts.** Android back gestures from the screen edge
  compete with our edge swipe. Use a configurable edge width, and exclusion
  rects in the fork if needed.
- **Notifications.** A WebView app gets no push while backgrounded. Nothing
  in the official docs covers this; it stays out of scope unless we research
  it separately.
- **VendroidEnhanced.** The Vendroid README recommends it. The theme
  (path A) should just work there. Plugin and fork compatibility isn't
  researched, since its docs weren't part of this pass. It's a candidate for
  a later milestone.
- **Upstreaming.** If we propose `mobileUX` to Vencord:
  - Open a feature request first.
  - Remove anything a stylesheet could do.
  - Follow the AI policy: disclose the tools, keep text short, make sure
    every line is understood.
