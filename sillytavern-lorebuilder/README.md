# sillytavern-lorebuilder

A SillyTavern extension ("Lore Builder") that lets the AI write your Lorebook while you brainstorm with it.
You talk through characters, places and rules in a normal chat. When something is settled, the AI saves it as a
Lorebook entry itself, using SillyTavern's built-in function calling. Plain JS, no build step. Tested against SillyTavern 1.19.

## What the AI can do

| Tool | What it does |
| --- | --- |
| `lore_list` | Lists the entries in the lorebook (uid, title, keywords, always-on), so it updates instead of duplicating. |
| `lore_read` | Reads one entry in full. |
| `lore_write` | Creates an entry, or updates one by uid: title, trigger keywords, content, always-on. |
| `lore_delete` | Deletes an entry. **You get a Yes/No popup first**, and "No" keeps it. |
| `lore_create_book` | Makes a new empty lorebook and switches to it. |

Changes are saved straight to the lorebook file. If ST's **World Info** panel is open, you see them appear there.
New entries get ST's default settings (position, depth, order, etc.), so tweak them in the World Info panel if you need to.

## Setup

1. Use **Chat Completion** with a model that supports tools. Claude, GPT, Gemini, DeepSeek and most OpenRouter models do.
2. In the **AI Response Configuration** panel (the sliders icon), tick **Enable function calling**.
3. In *Extensions → Lore Builder*, pick the lorebook the AI should build, or click **New**. The status line there tells you
   whether function calling is on.
4. Open a chat (any character, or a "Brainstorm" one) and brainstorm. You can say things like:
   - "Let's build the world for my story. Save each character and place to the lorebook once we agree on it."
   - "Update Mara's entry: she's actually the captain's sister."
   - "Look at the lorebook and tell me what's missing."

The lorebook isn't switched on for your chats automatically. When you start writing the story, turn it on for that chat
or character as usual in the World Info panel.

## Install (Docker)

Same as [Mobile Writer](../sillytavern-mobile/). Clone the repo next to your `docker-compose.yml`, then add this to `volumes:`:

```yaml
      - ./stvb/sillytavern-lorebuilder:/home/node/app/data/default-user/extensions/sillytavern-lorebuilder
```

Then run `docker compose up -d` and reload the page. Or copy the folder instead:
`cp -r stvb/sillytavern-lorebuilder ./data/default-user/extensions/`.

## Install (no Docker)

```sh
git clone https://github.com/ArielNya/shit-i-vibecoded-while-bored ~/stvb
ln -s ~/stvb/sillytavern-lorebuilder ~/SillyTavern/data/default-user/extensions/sillytavern-lorebuilder
```

ST's "Install extension" button can't install this extension, because it lives in a subfolder of a monorepo.

## Checks before pushing

Run `node sillytavern-lorebuilder/lore.test.mjs`. Then run ST with the extension linked into `data/default-user/extensions/`,
tick *Enable function calling*, and in the browser console call each tool with
`SillyTavern.getContext().ToolManager.invokeFunctionTool('lore_write', {...})`. Check these:

- With no lorebook picked, the tools return an error message instead of failing.
- `lore_create_book` creates the book and selects it in the drawer.
- `lore_write` creates entries, and updating by uid changes only the fields you pass.
- `lore_delete` shows the popup. "No" keeps the entry, "Yes" removes it.
- The entries show in ST's World Info panel.
