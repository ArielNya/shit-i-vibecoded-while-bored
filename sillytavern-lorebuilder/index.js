import { extension_settings, getContext } from '../../../extensions.js';
import { saveSettingsDebounced } from '../../../../script.js';
import { createNewWorldInfo, createWorldInfoEntry } from '../../../world-info.js';
import { POSITIONS, ROLES, STRATEGIES, describeEntry, listEntries, writeEntry } from './lore.js';

const NAME = 'sillytavern_lorebuilder';
const settings = extension_settings[NAME] = { book: '', ...extension_settings[NAME] };

function setBook(name) {
    settings.book = name;
    saveSettingsDebounced();
    renderSettings();
    // Select it in ST's World Info editor, which is where you watch the entries appear.
    if (name) getContext().reloadWorldInfoEditor(name, true);
}

async function loadBook() {
    if (!settings.book) throw new Error('No lorebook is selected. Ask the user to pick one in Extensions → Lore Builder, or call lore_create_book.');
    const data = await getContext().loadWorldInfo(settings.book);
    if (!data) throw new Error(`Lorebook "${settings.book}" was not found.`);
    // loadWorldInfo hands back ST's cache; edit a copy so a failed save leaves the cache as it was.
    return structuredClone(data);
}

async function saveBook(data) {
    const { saveWorldInfo, reloadWorldInfoEditor } = getContext();
    await saveWorldInfo(settings.book, data, true);
    reloadWorldInfoEditor(settings.book);
}

const schema = (properties = {}, required = []) => ({ $schema: 'http://json-schema.org/draft-04/schema#', type: 'object', properties, required });
const uid = { type: 'integer', description: 'The entry uid from lore_list.' };

const TOOLS = [
    {
        name: 'lore_list',
        displayName: 'Lore: list entries',
        description: 'List every entry in the lorebook being built (uid, title, trigger keywords, strategy, position, depth, order). Call this before writing so you update existing entries instead of making duplicates.',
        parameters: schema(),
        action: async () => ({ lorebook: settings.book, entries: listEntries(await loadBook()) }),
        formatMessage: () => 'Lore: reading the entry list',
    },
    {
        name: 'lore_read',
        displayName: 'Lore: read entry',
        description: 'Read the full content of one lorebook entry.',
        parameters: schema({ uid }, ['uid']),
        action: async ({ uid }) => {
            const entry = (await loadBook()).entries[uid];
            if (!entry) throw new Error(`No entry with uid ${uid}.`);
            return { ...describeEntry(entry), content: entry.content };
        },
        formatMessage: ({ uid }) => `Lore: reading entry ${uid}`,
    },
    {
        name: 'lore_write',
        displayName: 'Lore: write entry',
        description: 'Create a lorebook entry, or update one by passing its uid. Use it when the user and you settle a character, place, faction, item, event or rule while brainstorming. Write the content as compact third-person facts the story AI can use later. Only the fields you pass are changed; leave strategy, position, depth, role and order out unless the user asks for them or the entry clearly needs it.',
        parameters: schema({
            uid: { ...uid, description: 'Leave out to create a new entry. Pass it to update that entry.' },
            title: { type: 'string', description: 'Short name of the entry, e.g. "Mara Voss" or "Ashford Keep".' },
            keys: { type: 'array', items: { type: 'string' }, description: 'Trigger keywords: names, nicknames and words that should bring this entry into the story prompt.' },
            content: { type: 'string', description: 'The entry text.' },
            strategy: { type: 'string', enum: STRATEGIES, description: 'When the entry is inserted. "keyword" (default): when a trigger keyword shows up in the chat. "constant": always, so only for core facts like world rules or the premise. "vectorized": by meaning, needs the Vector Storage extension.' },
            position: { type: 'string', enum: Object.keys(POSITIONS), description: 'Where it goes in the prompt: before_char / after_char (around the character description, default before_char), an_top / an_bottom (around the Author\'s Note), em_top / em_bottom (around the example messages), at_depth (inside the chat history, see depth).' },
            depth: { type: 'integer', minimum: 0, description: 'Only for position at_depth: how many messages up from the newest one. 0 is the very bottom (strongest effect), ST default is 4.' },
            role: { type: 'string', enum: Object.keys(ROLES), description: 'Only for position at_depth: which role the inserted message has. Default system.' },
            order: { type: 'integer', minimum: 0, description: 'Insertion order among entries at the same position. Higher goes later, closer to the end of the prompt. ST default is 100.' },
        }),
        action: async args => {
            const data = await loadBook();
            const entry = writeEntry(data, args, d => createWorldInfoEntry(settings.book, d));
            await saveBook(data);
            return { saved: true, uid: entry.uid, title: entry.comment };
        },
        formatMessage: ({ title, uid }) => `Lore: writing ${title ? `"${title}"` : `entry ${uid}`}`,
    },
    {
        name: 'lore_delete',
        displayName: 'Lore: delete entry',
        description: 'Delete a lorebook entry. The user is asked to confirm first.',
        parameters: schema({ uid }, ['uid']),
        action: async ({ uid }) => {
            const { callGenericPopup, POPUP_TYPE } = getContext();
            const data = await loadBook();
            const entry = data.entries[uid];
            if (!entry) throw new Error(`No entry with uid ${uid}.`);
            const ok = await callGenericPopup(`Let the AI delete the lorebook entry "${entry.comment || uid}" from ${settings.book}?`, POPUP_TYPE.CONFIRM);
            if (!ok) return { deleted: false, reason: 'The user said no. Keep the entry.' };
            delete data.entries[uid];
            await saveBook(data);
            return { deleted: true, uid };
        },
        formatMessage: ({ uid }) => `Lore: deleting entry ${uid}`,
    },
    {
        name: 'lore_create_book',
        displayName: 'Lore: new lorebook',
        description: 'Create a new empty lorebook and make it the one being built. Only when the user asks for a new lorebook.',
        parameters: schema({ name: { type: 'string', description: 'Lorebook name, usually the story title.' } }, ['name']),
        action: async ({ name }) => {
            const exists = getContext().getWorldInfoNames().includes(name);
            if (!exists && !await createNewWorldInfo(name)) throw new Error(`Couldn't create lorebook "${name}".`);
            setBook(name);
            return { lorebook: name, created: !exists };
        },
        formatMessage: ({ name }) => `Lore: creating lorebook "${name}"`,
    },
];

// Errors go back to the model as text, so it can fix the call instead of the turn failing.
const safe = action => async args => {
    try {
        return await action(args ?? {});
    } catch (error) {
        return `Error: ${error.message}`;
    }
};

const esc = s => String(s).replace(/[&<>"]/g, c => `&#${c.charCodeAt(0)};`);

function renderSettings() {
    const { getWorldInfoNames, isToolCallingSupported } = getContext();
    const names = getWorldInfoNames();
    $('#lb_book').html(`<option value="">— pick a lorebook —</option>${names.map(n => `<option value="${esc(n)}">${esc(n)}</option>`).join('')}`).val(names.includes(settings.book) ? settings.book : '');
    $('#lb_status').text(isToolCallingSupported()
        ? 'Function calling is on. Ask the AI to save what you brainstorm into the lorebook.'
        : 'Function calling is off. Use Chat Completion and tick "Enable function calling" in the AI Response settings.');
}

const settingsHtml = `
<div class="inline-drawer">
    <div class="inline-drawer-toggle inline-drawer-header">
        <b>Lore Builder</b>
        <div class="inline-drawer-icon fa-solid fa-circle-chevron-down down"></div>
    </div>
    <div class="inline-drawer-content">
        <label for="lb_book">Lorebook the AI builds</label>
        <div class="flex-container">
            <select id="lb_book" class="text_pole flex1"></select>
            <div id="lb_new" class="menu_button menu_button_icon"><i class="fa-solid fa-plus"></i>New</div>
        </div>
        <small id="lb_status"></small>
    </div>
</div>`;

jQuery(() => {
    const { registerFunctionTool, eventSource, eventTypes, callGenericPopup, POPUP_TYPE } = getContext();
    TOOLS.forEach(t => registerFunctionTool({ ...t, action: safe(t.action), shouldRegister: () => true }));

    $('#extensions_settings2').append(settingsHtml);
    $('#lb_book').on('change', e => setBook(e.target.value));
    // Lorebooks made or deleted in ST's own editor show up the next time you open this drawer.
    $('#lb_book').closest('.inline-drawer').find('.inline-drawer-toggle').on('click', renderSettings);
    $('#lb_new').on('click', async () => {
        const name = String(await callGenericPopup('Name of the new lorebook:', POPUP_TYPE.INPUT, '') || '').trim();
        if (name && await createNewWorldInfo(name, { interactive: true })) setBook(name);
    });
    eventSource.on(eventTypes.SETTINGS_UPDATED, renderSettings);
    renderSettings();
});
