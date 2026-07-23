(function (root, factory) {
    const api = factory();
    if (typeof module !== 'undefined' && module.exports) {
        module.exports = api;
    }
    if (root) {
        root.ResumableStream = api;
    }
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
    function parseBlock(block) {
        let id = '';
        let event = 'message';
        const dataLines = [];

        for (const line of block.split(/\r?\n/)) {
            if (!line || line.startsWith(':')) continue;
            const separator = line.indexOf(':');
            const field = separator === -1 ? line : line.slice(0, separator);
            let value = separator === -1 ? '' : line.slice(separator + 1);
            if (value.startsWith(' ')) value = value.slice(1);
            if (field === 'id') id = value;
            else if (field === 'event') event = value;
            else if (field === 'data') dataLines.push(value);
        }

        if (!dataLines.length) return null;
        const rawData = dataLines.join('\n');
        let data = rawData;
        try {
            data = JSON.parse(rawData);
        } catch (_) {
            // Plain-text SSE data is valid and should be passed through unchanged.
        }
        return { id, event, data };
    }

    function createParser(onEvent) {
        let buffer = '';

        function drain(final = false) {
            const normalized = buffer.replace(/\r\n/g, '\n');
            const blocks = normalized.split('\n\n');
            buffer = final ? '' : blocks.pop();
            const ready = final ? blocks.concat(buffer ? [buffer] : []) : blocks;
            for (const block of ready) {
                const event = parseBlock(block);
                if (event) onEvent(event);
            }
        }

        return {
            push(chunk) {
                buffer += chunk;
                drain(false);
            },
            finish() {
                drain(true);
            }
        };
    }

    async function readResponse(response, onEvent) {
        if (!response.body) throw new Error('浏览器不支持流式响应');
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        const parser = createParser(onEvent);
        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            parser.push(decoder.decode(value, { stream: true }));
        }
        parser.push(decoder.decode());
        parser.finish();
    }

    function applyCursor(active, event) {
        return event && event.id ? { ...active, cursor: event.id } : { ...active };
    }

    return { createParser, readResponse, applyCursor };
});
