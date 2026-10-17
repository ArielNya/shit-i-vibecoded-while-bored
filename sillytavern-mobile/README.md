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
  - **Prompts**: a full-screen list of your preset's prompts with big switches (see below).
- **Larger story text** (size is adjustable) and slimmer margins. Avatars are smaller.
- **44px tap targets** for the swipe arrows, message buttons, send/continue and the top-bar icons.
- **Keyboard fix**: the chat resizes to the visible area when the Android keyboard opens.
- **Solid drawers**: the settings panels no longer let chat text show through, and they scroll inside themselves.

The **Paige theme** works on desktop and mobile. It's the dark violet look from
[deiomo](https://deiomo.github.io/) (Writer's Block / Paige), and its colours come from
the CSS of that site. It recolours ST's own theme variables, so turning it off brings your normal theme back.

## Prompts sheet and default presets

The **Prompts** button opens the active Chat Completion preset as a list you can search, split into
collapsible sections. Section breaks come from the preset's own header prompts
(`---Tense---` in Writer's Block, `👁️ 01. POINT OF VIEW ══════` in Sola).

- **Pick-one groups** act like radio buttons: turning one on turns the others off. Tap the one that's on to turn it off.
  A group comes from a header that says "Pick One", from Sola's `[PICK 1: POV]` tags,
  or from its `[PICK 1: ↓]` / `[PICK 1: ↑]` pairs. Writer's Block sections that don't say "Pick One" (Tense, Response Length…) stay free toggles, so follow the preset's own advice for those.
- The list leaves out the prompts the authors say to leave alone (`DO NOT TOUCH`, `LEAVE THIS ON`, `README`), the header prompts and ST's markers. ST's own Prompt Manager still shows all of them.
- A toggle works the same as one in ST's Prompt Manager. Tap ST's preset **Save** to keep it in the preset file.

At the top are the two default presets, **Sola V3** (Flame) and **Writer's Block V2** (Writer's Block Unlimited V2).
If you already have one of them, its button switches to it. If you don't, the button downloads the preset from its
author's GitHub and passes it to ST's own importer. That importer then asks whether to allow the preset's
embedded regex scripts. Say yes, because the trackers and HTML need them. Chat Completion must be the active API.

The presets aren't bundled here, so you always get the authors' latest version:
- Sola: [pyrxpia/sola-hub](https://github.com/pyrxpia/sola-hub), © pyrxpia ([site](https://pyrxpia.github.io/sola-hub/))
- Writer's Block Unlimited: [deiomo/Writer-s-Block-Unlimited](https://github.com/deiomo/Writer-s-Block-Unlimited), © deiomo, MIT ([site](https://deiomo.github.io/))

## Settings

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

Run `node sillytavern-mobile/groups.test.mjs` (it checks the prompt grouping rules). Then run ST (`node server.js`) with the extension symlinked into
`data/default-user/extensions/`. Then open it in Chromium with Pixel 7 emulation
(Playwright works) and check these:

- The writer bar is visible, and the page has no horizontal scroll.
- **Edit last** fills the screen, and its ✓ / ✕ buttons work.
- **Read** hides the top bar and the input box.
- Drawers open solid.
- With Chat Completion on, **Prompts → Writer's Block V2 / Sola V3** imports and selects the preset.
  (In a sandbox, `page.route` the raw.githubusercontent.com URLs to local copies.) Pick-one rows switch each other off,
  and ST's Prompt Manager shows the same state.
- At desktop width the bar is gone.

On a real phone, also open the keyboard and check that the input box stays above it.
An emulator can't test that.
