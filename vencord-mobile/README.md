# Vencord Mobile UX

A touch-first theme and browser-only Vencord userplugin for VendroidEnhanced.
Development uses a narrow Discord Canary window so the
same CSS and web APIs can be exercised before moving the bundle to Android.

The project is intentionally split in two:

- `theme/MobileUX.theme.css` works in VendroidEnhanced as an Online Theme.
- `plugin/mobileUX/index.tsx` contains behavior that CSS cannot provide. It is
  included in both builds for Canary testing, but imports only browser-safe
  Vencord APIs so the exact same source runs in VendroidEnhanced.

No Electron, Node, or `native.ts` Vencord API is used by the plugin.

M1's theme implementation is complete and passes the desktop Canary responsive
suite. Android IME, safe-area, and VendroidEnhanced checks remain before the M1
acceptance gate can be closed.

## Local build

The helper expects an official Vencord checkout at `.vendor/Vencord` and
copies the userplugin into it before building:

```powershell
.\scripts\build.ps1
```

Override either tool path when they are not on `PATH`:

```powershell
.\scripts\build.ps1 -PnpmPath C:\path\to\pnpm.exe -NodeDirectory C:\path\to\node
```

Outputs are copied to `build/`. The source checkout and local runtimes are
ignored by git.

## Desktop test loop

1. Build, then inject the development build into Discord Canary (or copy the
   plugin into the source tree used by the existing patched install).
2. Enable **Mobile UX** in Vencord settings and set **Activation** to
   **Always on (testing)**.
3. Resize Canary through the phone-width presets in `TESTING.md`.
4. Keep DevTools open and verify that no `MobileUX` errors are logged.

The theme also activates automatically below 900 CSS pixels when the primary
pointer is coarse. The plugin's testing mode adds `html.mux-mobile`, allowing
the same rules to be checked in desktop Canary.

See [PLAN.md](PLAN.md) for milestones and [TESTING.md](TESTING.md) for the
responsive test matrix.
