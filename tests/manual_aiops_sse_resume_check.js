const assert = require('assert');

const ResumableStream = require('../static/resumableStream.js');

const baseUrl = process.env.AIOPS_BASE_URL || 'http://127.0.0.1:9900';

async function main() {
    const sessionId = `aiops_resume_e2e_${Date.now()}`;
    const controller = new AbortController();
    const firstResponse = await fetch(`${baseUrl}/api/aiops`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId }),
        signal: controller.signal
    });
    assert.strictEqual(firstResponse.status, 200);
    const streamId = firstResponse.headers.get('x-stream-id');
    assert.ok(streamId, 'missing X-Stream-ID header');

    let cursor = '0-0';
    let firstType = '';
    const intentionalDisconnect = new Error('intentional disconnect');
    try {
        await ResumableStream.readResponse(firstResponse, event => {
            if (event.id) cursor = event.id;
            if (event.data && event.data.type !== 'stream_start') {
                firstType = event.data.type;
                controller.abort();
                throw intentionalDisconnect;
            }
        });
    } catch (error) {
        if (error !== intentionalDisconnect && error.name !== 'AbortError') throw error;
    }
    assert.ok(firstType, 'first subscription received no AIOps event');

    await new Promise(resolve => setTimeout(resolve, 1200));
    const resumedResponse = await fetch(
        `${baseUrl}/api/streams/${streamId}?after=${encodeURIComponent(cursor)}`
    );
    assert.strictEqual(resumedResponse.status, 200);

    const resumedIds = [];
    const resumedTypes = [];
    let complete = false;
    await ResumableStream.readResponse(resumedResponse, event => {
        if (event.id) resumedIds.push(event.id);
        if (event.data && event.data.type) resumedTypes.push(event.data.type);
        if (event.data && ['done', 'complete'].includes(event.data.type)) complete = true;
        if (event.data && event.data.type === 'error') {
            throw new Error(event.data.data || event.data.message);
        }
    });

    assert.ok(complete, 'resumed AIOps subscription did not receive completion');
    assert.ok(resumedTypes.length > 0, 'resumed AIOps subscription received no events');
    assert.ok(!resumedIds.includes(cursor), 'AIOps resume replayed the acknowledged event');
    console.log(JSON.stringify({ streamId, cursor, firstType, resumedTypes, complete }));
}

main().catch(error => {
    console.error(error);
    process.exit(1);
});
