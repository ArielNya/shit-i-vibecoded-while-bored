# Responsive test matrix

Use Discord Canary with the **Mobile UX** plugin enabled and Activation set to
**Always on (testing)**. Test each viewport at 100% zoom.

| Preset | CSS viewport | Main pressure point |
| --- | ---: | --- |
| Small phone portrait | 360 x 640 | composer, menus, modal width |
| Modern phone portrait | 390 x 844 | baseline one-handed layout |
| Large phone portrait | 430 x 932 | member/profile slide-over |
| Phone landscape | 844 x 390 | short-height modals and composer |
| Foldable/tablet boundary | 900 x 700 | last mobile breakpoint |
| Desktop control | 1100 x 800 | mobile rules must be inactive in Auto |

For every mobile preset:

- Open a channel, DM, thread, forum post, member list, and user profile.
- Send, edit, reply to, react to, and copy text from a message.
- Open emoji/GIF/sticker pickers and upload a file.
- Open Vencord Settings, search plugins, and open a plugin settings modal.
- Tab through interactive controls; focused message actions must be visible.
- Verify code blocks scroll horizontally without widening the page.
- Check that interactive rows and buttons have a 44 px minimum hit area.
- Repeat at 125% text scaling and with reduced motion enabled.

Android-only checks (once the VendroidEnhanced test bundle exists): keyboard resize,
safe-area insets, long press, system back, rotation, and offline cold start.

## Automated Canary checks

With Canary running on remote-debugging port 9222:

```powershell
node .\scripts\test-canary.mjs
node .\scripts\inspect-m1.mjs
node .\scripts\test-channel-layout.mjs
node .\scripts\test-long-press.mjs
node .\scripts\test-m3-back.mjs
```

The latest M1 pass is stored under `build/test-results/`. At 390 x 844 the
channel occupied the full viewport, the composer remained visible, the sidebar
opened as an overlay, Vencord's plugin grid was one column, its settings modal
was full-screen, and no measured mobile target was under 44 px. Chromium's
`isMobile` emulation is used only for coarse-pointer/media-query coverage;
channel geometry is tested with a narrow desktop viewport because Canary's
unsupported mobile-web shell unmounts the chat pane.

M1 is not considered device-complete until the theme is exercised in stock
VendroidEnhanced with the Android keyboard open and real safe-area insets present.

M3 Canary results: the long-press check opens message, avatar, and guild-channel
menus; the back check closes an open context menu before calling the original
VendroidEnhanced back handler and confirms the MobileUX root classes stay active.
