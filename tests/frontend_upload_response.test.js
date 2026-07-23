const assert = require('assert');
const uploadResponse = require('../static/uploadResponse.js');

const queued = {
    task_id: 'task-1',
    state: 'PENDING',
    status_url: '/api/tasks/task-1',
    filename: 'cpu_high_usage.md'
};

assert.strictEqual(uploadResponse.isUploadSuccessResponse(queued), true);
assert.strictEqual(uploadResponse.isUploadQueuedResponse(queued), true);
assert.strictEqual(
    uploadResponse.getUploadTaskMessage('cpu_high_usage.md', { state: 'SUCCESS' }),
    'cpu_high_usage.md 文件成功上传到知识库'
);
assert.strictEqual(
    uploadResponse.resolveStatusUrl(
        'http://localhost:9900/api',
        '/api/tasks/task-1'
    ),
    'http://localhost:9900/api/tasks/task-1'
);
assert.strictEqual(
    uploadResponse.resolveStatusUrl('/api', '/api/tasks/task-1'),
    '/api/tasks/task-1'
);
assert.strictEqual(
    uploadResponse.resolveStatusUrl('/api', 'tasks/task-1'),
    '/api/tasks/task-1'
);
assert.strictEqual(uploadResponse.isUploadSuccessResponse({ message: 'failed' }), false);

console.log('frontend upload response tests passed');
