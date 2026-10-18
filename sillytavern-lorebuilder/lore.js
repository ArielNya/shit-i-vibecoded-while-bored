// Pure helpers on ST's World Info data ({ entries: { [uid]: entry } }), so they run under node for tests.

export const listEntries = data => Object.values(data.entries).map(e => ({
    uid: e.uid, title: e.comment, keys: e.key, always_on: !!e.constant,
}));

// create(data) must add a new entry with ST's defaults and return it (ST's createWorldInfoEntry).
export function writeEntry(data, { uid, title, keys, content, constant }, create) {
    const entry = uid === undefined || uid === null ? create(data) : data.entries[uid];
    if (!entry) throw new Error(`No entry with uid ${uid}. Call lore_list to see the uids.`);
    if (title !== undefined) entry.comment = String(title);
    if (keys !== undefined) entry.key = [...new Set([].concat(keys).map(k => String(k).trim()).filter(Boolean))];
    if (content !== undefined) entry.content = String(content);
    if (constant !== undefined) entry.constant = !!constant;
    return entry;
}
