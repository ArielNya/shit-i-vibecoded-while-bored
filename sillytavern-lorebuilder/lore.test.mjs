// Run: node sillytavern-lorebuilder/lore.test.mjs
import assert from 'node:assert/strict';
import { listEntries, writeEntry } from './lore.js';

const create = data => (data.entries[Object.keys(data.entries).length] = { uid: Object.keys(data.entries).length, key: [], comment: '', content: '', constant: false });
const data = { entries: {} };

const made = writeEntry(data, { title: 'Ashford Keep', keys: [' Ashford ', 'keep', 'keep', ''], content: 'A ruined fort.' }, create);
assert.deepEqual(made.key, ['Ashford', 'keep']);
assert.equal(made.uid, 0);

writeEntry(data, { uid: 0, content: 'A ruined fort on the cliffs.', constant: true }, create);
assert.equal(data.entries[0].content, 'A ruined fort on the cliffs.');
assert.equal(data.entries[0].comment, 'Ashford Keep', 'fields not passed stay as they were');

assert.throws(() => writeEntry(data, { uid: 7, content: 'x' }, create), /No entry with uid 7/);
assert.deepEqual(writeEntry(data, { keys: 'Mara' }, create).key, ['Mara'], 'a single key string becomes a list');
assert.deepEqual(listEntries(data), [
    { uid: 0, title: 'Ashford Keep', keys: ['Ashford', 'keep'], always_on: true },
    { uid: 1, title: '', keys: ['Mara'], always_on: false },
]);
console.log('lore ok');
