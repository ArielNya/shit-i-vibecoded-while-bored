// Run: node sillytavern-mobile/words.test.mjs
import assert from 'node:assert/strict';
import { countWords } from './words.js';

assert.equal(countWords('The rain   kept falling.\n\nShe waited.'), 6);
assert.equal(countWords('<p>One<br>two</p> <b>three</b>'), 3);
assert.equal(countWords(''), 0);
assert.equal(countWords(undefined), 0);
console.log('words ok');
