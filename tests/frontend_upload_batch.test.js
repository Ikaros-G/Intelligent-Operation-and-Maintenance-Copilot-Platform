const assert = require('assert');
const fs = require('fs');
const path = require('path');
const uploadBatch = require('../static/uploadBatch.js');

const validFile = (name, size = 1024) => ({ name, size });

const selection = uploadBatch.validateSelection([
    validFile('cpu.md'),
    validFile('notes.pdf'),
    validFile('large.txt', 51 * 1024 * 1024)
]);

assert.deepStrictEqual(selection.accepted.map(file => file.name), ['cpu.md']);
assert.deepStrictEqual(
    selection.rejected.map(item => item.reason),
    ['unsupported_type', 'file_too_large']
);

const tooMany = uploadBatch.validateSelection(
    Array.from({ length: 11 }, (_, index) => validFile(`file-${index}.md`))
);
assert.strictEqual(tooMany.tooMany, true);
assert.strictEqual(tooMany.accepted.length, 0);

const uploadSummary = uploadBatch.buildUploadSummary([
    { name: 'redis_connection_failure.md', state: 'SUCCESS' },
    { name: 'service_unavailable.md', state: 'SUCCESS' },
    { name: 'slow_response.md', state: 'SUCCESS' }
]);
assert.strictEqual(uploadSummary.title, 'redis_connection_failure.md 等 3 个文件上传成功');
assert.match(uploadSummary.markdown, /<details>/);
assert.match(uploadSummary.markdown, /service_unavailable\.md/);

const mixedSummary = uploadBatch.buildUploadSummary([
    { name: 'cpu.md', state: 'SUCCESS' },
    { name: 'bad.md', state: 'FAILURE', error: '索引失败' },
    { name: 'pending.md', state: 'PENDING' }
]);
assert.strictEqual(mixedSummary.title, 'cpu.md 上传成功，1 个失败，1 个处理中');
assert.match(mixedSummary.markdown, /bad\.md：失败，索引失败/);

(async () => {
    const visited = [];
    const results = await uploadBatch.runSequentially(['a', 'b', 'c'], async item => {
        visited.push(item);
        if (item === 'b') {
            throw new Error('failed');
        }
        return item.toUpperCase();
    });

    assert.deepStrictEqual(visited, ['a', 'b', 'c']);
    assert.deepStrictEqual(results.map(result => result.status), [
        'fulfilled',
        'rejected',
        'fulfilled'
    ]);

    const html = fs.readFileSync(path.join(__dirname, '../static/index.html'), 'utf8');
    const app = fs.readFileSync(path.join(__dirname, '../static/app.js'), 'utf8');
    assert.match(html, /<input[^>]+id="fileInput"[^>]+multiple/);
    assert.match(html, /\/static\/uploadBatch\.js\?v=/);
    assert.match(html, /\/static\/app\.js\?v=/);
    assert.ok(html.indexOf('/static/uploadBatch.js') < html.indexOf('/static/app.js'));
    assert.doesNotMatch(app, /!\s*messageElement\s*\|\|\s*!window\.UploadBatch\?\.buildUploadSummary/);

    console.log('frontend upload batch tests passed');
})().catch(error => {
    console.error(error);
    process.exit(1);
});
