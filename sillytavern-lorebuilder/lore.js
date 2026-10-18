// Pure helpers on ST's World Info data ({ entries: { [uid]: entry } }), so they run under node for tests.

// Names the model sees → ST's world_info_position numbers. The "outlet" position (7) is left out: it needs an outlet name.
export const POSITIONS = { before_char: 0, after_char: 1, an_top: 2, an_bottom: 3, at_depth: 4, em_top: 5, em_bottom: 6 };
export const ROLES = { system: 0, user: 1, assistant: 2 };
export const STRATEGIES = ['keyword', 'constant', 'vectorized'];

const nameOf = (table, value) => Object.keys(table).find(k => table[k] === value) ?? String(value);
const strategyOf = e => e.constant ? 'constant' : e.vectorized ? 'vectorized' : 'keyword';

export const describeEntry = e => ({
    uid: e.uid,
    title: e.comment,
    keys: e.key,
    strategy: strategyOf(e),
    position: nameOf(POSITIONS, e.position),
    ...(e.position === POSITIONS.at_depth && { depth: e.depth, role: nameOf(ROLES, e.role ?? 0) }),
    order: e.order,
});

export const listEntries = data => Object.values(data.entries).map(describeEntry);

function pick(table, value, field) {
    if (!(value in table)) throw new Error(`Unknown ${field} "${value}". Use one of: ${Object.keys(table).join(', ')}.`);
    return table[value];
}

function wholeNumber(value, field) {
    const n = Number(value);
    if (!Number.isInteger(n) || n < 0) throw new Error(`${field} must be a whole number of 0 or more, got "${value}".`);
    return n;
}

// create(data) must add a new entry with ST's defaults and return it (ST's createWorldInfoEntry).
// Everything is validated before anything is changed, so a bad call never leaves a half-written entry.
export function writeEntry(data, { uid, title, keys, content, strategy, position, depth, role, order }, create) {
    if (uid !== undefined && uid !== null && !data.entries[uid]) throw new Error(`No entry with uid ${uid}. Call lore_list to see the uids.`);
    if (strategy !== undefined && !STRATEGIES.includes(strategy)) throw new Error(`Unknown strategy "${strategy}". Use one of: ${STRATEGIES.join(', ')}.`);
    const pos = position === undefined ? undefined : pick(POSITIONS, position, 'position');
    const roleNum = role === undefined ? undefined : pick(ROLES, role, 'role');
    const depthNum = depth === undefined ? undefined : wholeNumber(depth, 'depth');
    const orderNum = order === undefined ? undefined : wholeNumber(order, 'order');

    const entry = uid === undefined || uid === null ? create(data) : data.entries[uid];
    if (title !== undefined) entry.comment = String(title);
    if (keys !== undefined) entry.key = [...new Set([].concat(keys).map(k => String(k).trim()).filter(Boolean))];
    if (content !== undefined) entry.content = String(content);
    // Same pair of flags ST's own strategy dropdown sets.
    if (strategy !== undefined) {
        entry.constant = strategy === 'constant';
        entry.vectorized = strategy === 'vectorized';
    }
    if (pos !== undefined) entry.position = pos;
    if (depthNum !== undefined) entry.depth = depthNum;
    if (roleNum !== undefined) entry.role = roleNum;
    if (orderNum !== undefined) entry.order = orderNum;
    return entry;
}
