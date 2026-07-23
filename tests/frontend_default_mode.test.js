const assert = require('assert');
const fs = require('fs');
const path = require('path');

const app = fs.readFileSync(path.join(__dirname, '../static/app.js'), 'utf8');
const html = fs.readFileSync(path.join(__dirname, '../static/index.html'), 'utf8');

const streamDefaults = app.match(/this\.currentMode = 'stream'/g) || [];
assert.strictEqual(streamDefaults.length, 2);
assert.match(html, /id="currentModeText">流式</);
assert.match(html, /class="dropdown-item active" data-mode="stream"/);
assert.doesNotMatch(html, /class="dropdown-item active" data-mode="quick"/);

console.log('frontend default mode tests passed');
