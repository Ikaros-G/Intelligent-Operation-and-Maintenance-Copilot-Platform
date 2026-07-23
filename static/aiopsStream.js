(function (root, factory) {
    const api = factory();
    if (typeof module !== 'undefined' && module.exports) {
        module.exports = api;
    }
    if (root) {
        root.AIOpsStream = api;
    }
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
    function pad(value) {
        return String(value).padStart(2, '0');
    }

    function createSessionTitle(date = new Date()) {
        return `AI Ops 诊断 ${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
    }

    function createState() {
        return {
            content: '',
            done: false,
            error: '',
            reportStarted: false,
            reportContentStart: -1
        };
    }

    function startReport(state) {
        if (state.reportStarted) return state;
        const heading = '\n\n## 🎯 诊断报告\n\n';
        return {
            ...state,
            content: state.content + heading,
            reportStarted: true,
            reportContentStart: state.content.length + heading.length
        };
    }

    function applyEvent(previousState, event) {
        let state = { ...previousState };
        const message = event || {};

        if (message.type === 'plan') {
            const plan = Array.isArray(message.plan) ? message.plan : [];
            const planItems = plan.map((step, index) => `${index + 1}. ${step}`).join('\n');
            state.content += `\n\n## 📋 执行计划\n\n${message.message || ''}\n\n`;
            if (planItems) {
                state.content += `${planItems}\n\n`;
            }
        } else if (message.type === 'step_complete') {
            state.content += `- ✅ ${message.message || ''}\n\n`;
        } else if (message.type === 'status') {
            state.content += `- ⏳ ${message.message || ''}\n\n`;
        } else if (message.type === 'content' || message.type === 'report_chunk') {
            state = startReport(state);
            state.content += message.data || '';
        } else if (message.type === 'report_replace') {
            state = startReport(state);
            state.content = state.content.slice(0, state.reportContentStart) + (message.data || '');
        } else if (message.type === 'report') {
            if (!state.reportStarted) {
                state = startReport(state);
                state.content += message.report || '';
            }
        } else if (message.type === 'complete' || message.type === 'done') {
            state.done = true;
        } else if (message.type === 'error') {
            state.error = message.data || message.message || '智能运维分析失败';
        }

        return state;
    }

    return { createSessionTitle, createState, applyEvent };
});
