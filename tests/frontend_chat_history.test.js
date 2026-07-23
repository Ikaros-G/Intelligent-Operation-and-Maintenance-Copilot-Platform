const assert = require('assert');

const ChatHistory = require('../static/chatHistory.js');

const backendMessages = ChatHistory.normalizeMessages([
    { role: 'user', content: '如何排查内存问题？', timestamp: '2026-07-18T10:00:00Z' },
    { role: 'assistant', content: '## 排查步骤\n\n- 查看内存指标', timestamp: '2026-07-18T10:00:01Z' }
]);

assert.deepStrictEqual(
    backendMessages.map(message => message.type),
    ['user', 'assistant']
);
assert.strictEqual(backendMessages[1].content, '## 排查步骤\n\n- 查看内存指标');

const legacyMessages = ChatHistory.normalizeMessages([
    { type: 'bot', content: '**旧版助手消息**' }
]);
assert.strictEqual(legacyMessages[0].type, 'assistant');

const partialMessage = ChatHistory.normalizeMessage({
    type: 'assistant',
    content: 'partial',
    streamId: 'stream-1',
    streamKind: 'chat',
    streamStatus: 'running',
    lastEventId: '10-0',
    aiopsState: { content: 'partial', done: false }
});
assert.strictEqual(partialMessage.streamId, 'stream-1');
assert.strictEqual(partialMessage.streamStatus, 'running');
assert.strictEqual(partialMessage.lastEventId, '10-0');
assert.deepStrictEqual(partialMessage.aiopsState, { content: 'partial', done: false });

console.log('frontend chat history tests passed');
