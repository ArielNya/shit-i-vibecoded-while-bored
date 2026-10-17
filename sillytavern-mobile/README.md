# sillytavern-mobile

A SillyTavern extension ("Mobile Writer") for co-writing stories on a phone,
for when ST runs in Termux on Android. Plain CSS plus about 70 lines of JS, with no build step.
Tested against SillyTavern 1.19.

## What it does

On screens up to 1000px wide (ST's own mobile breakpoint):

- **Writer bar** above the input box with three buttons:
  - **Continue**: does the same thing as ST's own "Continue" menu item.
  - **Edit last**: opens the AI's last reply in ST's editor, expanded to full screen.
  - **Read**: hides everything except the story and the writer bar. Tap it again to exit.
- **Larger story text** (size is adjustable) and slimmer margins. Avatars are smaller.
- **44px tap targets** for the swipe arrows, message buttons, send/continue and the top-bar icons.
- **Keyboard fix**: the chat resizes to the visible area when the Android keyboard opens.
- **Solid drawers**: the settings panels no longer let chat text show through, and they scroll inside themselves.

The **Paige theme** works on desktop and mobile. It's the dark violet look from
[deiomo](https://deiomo.github.io/) (Writer's Block / Paige), and its colours come from
the CSS of that site. It recolours ST's own theme variables, so turning it off brings your normal theme back.

Settings live in *Extensions → Mobile Writer*: mobile layout on/off, Paige theme
on/off, and story text size.

## Install (Termux)

```sh
git clone https://github.com/ArielNya/shit-i-vibecoded-while-bored ~/stvb
ln -s ~/stvb/sillytavern-mobile ~/SillyTavern/data/default-user/extensions/sillytavern-mobile
```

Restart ST, then reload the page. ST's "Install extension" button can't install this
extension, because it lives in a subfolder of a monorepo.

To update:

```sh
cd ~/stvb && git pull
```

Then reload the page.

## Checks before pushing

There's no test suite. Run ST (`node server.js`) with the extension symlinked into
`data/default-user/extensions/`. Then open it in Chromium with Pixel 7 emulation
(Playwright works) and check these:

- The writer bar is visible, and the page has no horizontal scroll.
- **Edit last** fills the screen, and its ✓ / ✕ buttons work.
- **Read** hides the top bar and the input box.
- Drawers open solid.
- At desktop width the bar is gone.

On a real phone, also open the keyboard and check that the input box stays above it.
An emulator can't test that.
