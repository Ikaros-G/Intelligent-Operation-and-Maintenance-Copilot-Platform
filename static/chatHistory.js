(function (root, factory) {
    const api = factory();
    if (typeof module !== 'undefined' && module.exports) {
        module.exports = api;
    }
    if (root) {
        root.ChatHistory = api;
    }
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
    function normalizeMessage(message) {
        const source = message || {};
        const sourceType = source.type || source.role;
        const type = sourceType === 'user' ? 'user' : 'assistant';

        const normalized = {
            type,
            content: String(source.content || ''),
            timestamp: source.timestamp || new Date().toISOString()
        };

        for (const field of ['streamId', 'streamKind', 'streamStatus', 'lastEventId']) {
            if (source[field] !== undefined && source[field] !== null) {
                normalized[field] = String(source[field]);
            }
        }
        if (source.aiopsState && typeof source.aiopsState === 'object') {
            normalized.aiopsState = { ...source.aiopsState };
        }

        return normalized;
    }

    function normalizeMessages(messages) {
        return Array.from(messages || [], normalizeMessage);
    }

    return { normalizeMessage, normalizeMessages };
});
