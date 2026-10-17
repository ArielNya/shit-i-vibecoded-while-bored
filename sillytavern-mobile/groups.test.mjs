// Run: node sillytavern-mobile/groups.test.mjs  (names copied from Sola V3 Flame and Writer's Block Unlimited V2)
import assert from 'node:assert/strict';
import { groupPrompts } from './groups.js';

const names = [
    '(README! Intro to Writer\'s Block Unlimited) ',
    'GLM Jailbreak',
    '👁️ 01. POINT OF VIEW (POV) ══════════',
    'First-Person Present Tense [PICK 1: POV] ',
    'Third-Person Present Tense [PICK 1: POV] ',
    'He / Him [PICK 1: PRONOUN] ',
    'She / Her [PICK 1: PRONOUN] ',
    '📜 02. CORE FOUNDATIONS ══════════',
    '[PICK 1: ↓] Agency-Lite',
    '[PICK 1: ↑] Embellished User',
    'Oath',
    '[PICK 1: ↓] Anti-Slop Full',
    '[PICK 1: ↑] Anti-Slop Lite',
    'Story Grounding [PICK 1: GROUNDING] ',
    '🚫DO NOT TOUCH🚫 Pre-History: 🎀 Sola’s Master Blueprint',
    '---Narrative Modes--- (Pick One)',
    '🎬Director🎬(Input are directions that must be followed)',
    '👤Roleplay 👤(Does not write for you)',
    '---Tense---',
    'Present-Tense',
    'Past-Tense ',
    '(leave this prompt on)',
    'Tones Primer (DONT TOUCH)',
    'Story Grounding [PICK 1: GROUNDING] ',
    '  ',
];
const prompts = names.map((name, i) => ({ identifier: `p${i}`, name }));
prompts.push({ identifier: 'chatHistory', name: 'Chat History', marker: true });

const sections = groupPrompts(prompts);
const items = Object.fromEntries(sections.flatMap(s => s.items).map(i => [i.identifier, i]));
const group = i => items[`p${i}`]?.group;

assert.deepEqual(sections.map(s => s.title), ['General', '👁️ 01. POINT OF VIEW (POV)', '📜 02. CORE FOUNDATIONS', 'Narrative Modes (Pick One)', 'Tense']);
assert.equal(items.p0, undefined, 'README hidden');
assert.equal(group(1), null, 'plain prompt is a free toggle');
assert.equal(group(3), group(4), 'POV radio');
assert.notEqual(group(3), group(5), 'pronouns are their own group');
assert.equal(group(5), group(6));
assert.equal(group(8), group(9), '↓ pairs with the next ↑');
assert.equal(group(11), group(12));
assert.notEqual(group(8), group(11), 'each ↓↑ pair is separate');
assert.equal(group(10), null);
assert.equal(group(13), group(23), 'same tag across sections is one group');
assert.equal(items.p14, undefined, 'DO NOT TOUCH hidden');
assert.equal(group(16), group(17), 'Pick One header makes a radio section');
assert.equal(group(19), null, 'unlabelled sections stay free toggles');
assert.equal(items.p21, undefined);
assert.equal(items.p22, undefined);
assert.equal(items.p24, undefined, 'blank names skipped');
assert.equal(items.chatHistory, undefined, 'markers skipped');
console.log('groups ok');
