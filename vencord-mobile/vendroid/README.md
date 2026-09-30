# VendroidEnhanced integration

The Android fork starts in M4. Until then this directory documents the narrow
integration boundary for VendroidEnhanced:

- load `build/browser.js` and `build/browser.css` as web assets;
- use no Electron, Node, or `native.ts` implementation from the plugin (the
  source is intentionally shared with the desktop test build);
- expose the existing `window.VencordMobile.onBackPress` bridge only;
- leave layout and visual changes in `theme/MobileUX.theme.css`;
- set `adjustResize` and safe-area plumbing in the Android shell later.

VendroidEnhanced already accepts a custom Vencord bundle URL, so plugin testing
does not need an APK fork. Import its maintained Forgejo repository only if M4's
Android-shell changes still require one.
