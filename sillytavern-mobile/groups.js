// Splits a preset's prompt order into sections and pick-one groups, from the naming
// conventions Sola ("👁️ 01. POV ═══", "[PICK 1: POV]") and Writer's Block ("---Tense---", "(Pick One)") use.
const HEADER = /^\W*-{2,}|═{3,}/;
const PICK_SECTION = /pick\s*(one|1)\b/i;
const PICK_TAG = /\[PICK 1:\s*([^\]]+?)\s*\]/i;
const HIDDEN = /DO\s*N.?T\s*(TOUCH|ENABLE)|LEAVE THIS|README|READ ME/i;

/**
 * @param {{identifier: string, name?: string, marker?: boolean}[]} prompts in prompt-order
 * @returns {{title: string, items: {identifier: string, name: string, group: string|null}[]}[]}
 */
export function groupPrompts(prompts) {
    const sections = [{ title: 'General', items: [] }];
    let section = sections[0];
    let sectionGroup = null;
    let arrowGroup = null;
    let n = 0;

    for (const p of prompts) {
        const name = (p.name ?? '').trim();
        if (p.marker || !name) continue;
        if (HEADER.test(name)) {
            section = { title: name.replace(/-{2,}|═+/g, ' ').replace(/\s+/g, ' ').trim(), items: [] };
            sections.push(section);
            sectionGroup = PICK_SECTION.test(name) ? `section${++n}` : null;
            continue;
        }
        if (HIDDEN.test(name)) continue;

        const tag = name.match(PICK_TAG)?.[1];
        let group = sectionGroup;
        if (tag === '↓') {
            group = arrowGroup = `pair${++n}`;
        } else if (tag === '↑') {
            group = arrowGroup ?? `pair${++n}`;
            arrowGroup = null;
        } else if (tag) {
            group = `tag:${tag.toUpperCase()}`;
        }
        section.items.push({ identifier: p.identifier, name, group });
    }
    return sections.filter(s => s.items.length);
}
