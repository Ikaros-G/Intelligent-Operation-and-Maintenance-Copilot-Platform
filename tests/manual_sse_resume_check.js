const assert = require('assert');

const ResumableStream = require('../static/resumableStream.js');

const baseUrl = process.env.AIOPS_BASE_URL || 'http://127.0.0.1:9900';

async function main() {
    const sessionId = `resume_e2e_${Date.now()}`;
    const controller = new AbortController();
    const firstResponse = await fetch(`${baseUrl}/api/chat_stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            Id: sessionId,
            Question: '请用至少12个编号步骤说明 Linux CPU 占用率过高的严谨排查方法，每个步骤都说明目的。'
        }),
        signal: controller.signal
    });
    assert.strictEqual(firstResponse.status, 200);
    const streamId = firstResponse.headers.get('x-stream-id');
    assert.ok(streamId, 'missing X-Stream-ID header');

    let cursor = '0-0';
    let firstContent = '';
    const intentionalDisconnect = new Error('intentional disconnect');
    try {
        await ResumableStream.readResponse(firstResponse, event => {
            if (event.id) cursor = event.id;
            if (event.data && event.data.type === 'content') {
                firstContent += event.data.data || '';
                controller.abort();
                throw intentionalDisconnect;
            }
        });
    } catch (error) {
        if (error !== intentionalDisconnect && error.name !== 'AbortError') throw error;
    }
    assert.ok(firstContent.length > 0, 'first subscription received no content');

    await new Promise(resolve => setTimeout(resolve, 1200));
    const resumedResponse = await fetch(
        `${baseUrl}/api/streams/${streamId}?after=${encodeURIComponent(cursor)}`
    );
    assert.strictEqual(resumedResponse.status, 200);

    let remainingContent = '';
    let done = false;
    const resumedIds = [];
    await ResumableStream.readResponse(resumedResponse, event => {
        if (event.id) resumedIds.push(event.id);
        if (event.data && event.data.type === 'content') {
            remainingContent += event.data.data || '';
        }
        if (event.data && ['done', 'complete'].includes(event.data.type)) done = true;
        if (event.data && event.data.type === 'error') {
            throw new Error(event.data.data || event.data.message);
        }
    });

    assert.ok(done, 'resumed subscription did not receive completion');
    assert.ok(remainingContent.length > 0, 'resumed subscription received no remaining content');
    assert.ok(!resumedIds.includes(cursor), 'resume replayed the last acknowledged event');
    console.log(JSON.stringify({
        streamId,
        cursor,
        firstChars: firstContent.length,
        resumedChars: remainingContent.length,
        done
    }));
}

main().catch(error => {
    console.error(error);
    process.exit(1);
});
