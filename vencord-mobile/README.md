# vencord-mobile

A mobile-UX theme and plugin for [Vencord](https://github.com/Vendicated/Vencord)
running in [Vendroid](https://github.com/Vencord/Vendroid) on Android, plus a
Vendroid fork for startup, keyboard and back-button fixes. Design, sources and
milestones: [`PLAN.md`](PLAN.md).

**Status:** M0 (skeleton) and the M1 theme are written. The theme is linted and
tested in headless Chromium, but not yet checked against live Discord on a phone.

## Layout

| Path | What |
| --- | --- |
| `theme/MobileUX.theme.css` | The theme (PLAN.md §3). Works on stock Vendroid |
| `plugin/mobileUX.browser/` | The `MobileUX` userplugin (PLAN.md §4). Skeleton only in M0 |
| `vendroid/` | Fork of [Vencord/Vendroid](https://github.com/Vencord/Vendroid) at upstream `006ca4d`, kept as a git subtree. Unmodified so far; fork changes start in M4 |
| `scripts/build-vencord.sh` | Builds Vencord's `browser.js` / `browser.css` with the userplugin into `dist/` |
| `test/` | Theme tests (header parsing + headless Chromium) |

## Install the theme (stock Vendroid)

In Vendroid: **Settings › Vencord › Themes › Online Themes**, add

```
https://cdn.jsdelivr.net/gh/ArielNya/shit-i-vibecoded-while-bored@main/vencord-mobile/theme/MobileUX.theme.css
```

and enable it. (The raw.githubusercontent.com URL also works on Vendroid, which
serves any `.css` response as `text/css`.) Or download the file and use
**Local Themes › Upload Theme**.

The theme only applies on touch screens up to 900 px wide, so it's safe to keep
enabled on synced desktop clients. Tweak it in QuickCSS:

```css
:root { --mux-touch-target: 48px; --mux-font-scale: 1.1; }
```

## Development

Needs Node 22+ and pnpm 10.

```sh
pnpm install
pnpm check          # stylelint + tests (Chromium from /opt/pw-browsers, or set CHROMIUM_PATH)
```

The header test runs Vencord's own theme parser, so it's skipped until
`scripts/build-vencord.sh` has cloned Vencord into `.cache/`.

### Building Vencord with the plugin

```sh
./scripts/build-vencord.sh          # add --dev for a development build
```

This clones Vencord at the commit pinned in the script into `.cache/Vencord`,
copies `plugin/` into its `src/userplugins/`, runs `pnpm buildWebStandalone` and
copies `browser.js` + `browser.css` into `dist/`. It fails if `MobileUX` isn't in
the bundle. Vencord's install fetches a git dependency from
`codeload.github.com`, so that host must be reachable.

### Pulling upstream Vendroid changes

```sh
git subtree pull --prefix vencord-mobile/vendroid https://github.com/Vencord/Vendroid.git main --squash
```
