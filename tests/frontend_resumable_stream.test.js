const assert = require('assert');

const ResumableStream = require('../static/resumableStream.js');

const events = [];
const parser = ResumableStream.createParser(event => events.push(event));

parser.push('id: 10-0\nevent: message\ndata: {"type":"content",');
parser.push('"data":"hello"}\n\nid: 11-0\ndata: first line\n');
parser.push('data: second line\n\n');
parser.finish();

assert.deepStrictEqual(events[0], {
    id: '10-0',
    event: 'message',
    data: { type: 'content', data: 'hello' }
});
assert.deepStrictEqual(events[1], {
    id: '11-0',
    event: 'message',
    data: 'first line\nsecond line'
});

const active = ResumableStream.applyCursor(
    { cursor: '10-0', content: 'hello' },
    { id: '11-0', data: { type: 'content', data: ' world' } }
);
assert.deepStrictEqual(active, { cursor: '11-0', content: 'hello' });

console.log('frontend resumable stream tests passed');
