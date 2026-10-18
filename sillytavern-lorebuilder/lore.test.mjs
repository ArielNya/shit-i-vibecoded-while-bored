// Run: node sillytavern-lorebuilder/lore.test.mjs
import assert from 'node:assert/strict';
import { listEntries, writeEntry } from './lore.js';

// Same defaults as ST's newWorldInfoEntryTemplate for the fields we touch.
const create = data => {
    const uid = Object.keys(data.entries).length;
    return (data.entries[uid] = { uid, key: [], comment: '', content: '', constant: false, vectorized: false, position: 0, depth: 4, role: 0, order: 100 });
};
const data = { entries: {} };

const made = writeEntry(data, { title: 'Ashford Keep', keys: [' Ashford ', 'keep', 'keep', ''], content: 'A ruined fort.' }, create);
assert.deepEqual(made.key, ['Ashford', 'keep']);
assert.equal(made.uid, 0);

writeEntry(data, { uid: 0, content: 'A ruined fort on the cliffs.', strategy: 'constant', position: 'at_depth', depth: 2, role: 'assistant', order: 250 }, create);
assert.equal(data.entries[0].content, 'A ruined fort on the cliffs.');
assert.equal(data.entries[0].comment, 'Ashford Keep', 'fields not passed stay as they were');
assert.deepEqual([data.entries[0].constant, data.entries[0].position, data.entries[0].depth, data.entries[0].role, data.entries[0].order], [true, 4, 2, 2, 250]);

writeEntry(data, { uid: 0, strategy: 'vectorized' }, create);
assert.deepEqual([data.entries[0].constant, data.entries[0].vectorized], [false, true], 'strategy flags never both on');

assert.throws(() => writeEntry(data, { uid: 7, content: 'x' }, create), /No entry with uid 7/);
assert.throws(() => writeEntry(data, { uid: 0, position: 'top' }, create), /Unknown position "top"/);
assert.throws(() => writeEntry(data, { uid: 0, depth: -1 }, create), /depth must be a whole number/);
assert.throws(() => writeEntry(data, { strategy: 'blue', title: 'Nope' }, create), /Unknown strategy/);
assert.equal(Object.keys(data.entries).length, 1, 'a rejected create adds nothing');
assert.equal(data.entries[0].position, 4, 'a rejected update changes nothing');

assert.deepEqual(writeEntry(data, { keys: 'Mara' }, create).key, ['Mara'], 'a single key string becomes a list');
assert.deepEqual(listEntries(data), [
    { uid: 0, title: 'Ashford Keep', keys: ['Ashford', 'keep'], strategy: 'vectorized', position: 'at_depth', depth: 2, role: 'assistant', order: 250 },
    { uid: 1, title: '', keys: ['Mara'], strategy: 'keyword', position: 'before_char', order: 100 },
]);
console.log('lore ok');
