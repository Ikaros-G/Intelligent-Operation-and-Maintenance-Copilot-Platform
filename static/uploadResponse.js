(function (root, factory) {
    const api = factory();
    if (typeof module === 'object' && module.exports) {
        module.exports = api;
    }
    root.UploadResponse = api;
}(typeof globalThis !== 'undefined' ? globalThis : this, function () {
    function isUploadQueuedResponse(data) {
        return Boolean(data && data.task_id && data.status_url && data.state);
    }

    function isUploadSuccessResponse(data) {
        const legacySuccess = Boolean(
            data && (data.code === 200 || data.message === 'success') && data.data
        );
        return legacySuccess || isUploadQueuedResponse(data);
    }

    function getUploadTaskMessage(filename, status) {
        if (status && status.state === 'SUCCESS') {
            return `${filename} 文件成功上传到知识库`;
        }
        if (status && status.state === 'FAILURE') {
            return `${filename} 知识库索引失败：${status.error || '未知错误'}`;
        }
        return `${filename} 知识库索引仍在处理中，请稍后查看任务状态`;
    }

    function resolveStatusUrl(apiBaseUrl, statusUrl) {
        if (/^https?:\/\//i.test(statusUrl)) {
            return statusUrl;
        }

        if (statusUrl.startsWith('/')) {
            if (/^https?:\/\//i.test(apiBaseUrl)) {
                return new URL(statusUrl, new URL(apiBaseUrl).origin).toString();
            }
            return statusUrl;
        }

        if (/^https?:\/\//i.test(apiBaseUrl)) {
            const base = apiBaseUrl.endsWith('/') ? apiBaseUrl : `${apiBaseUrl}/`;
            return new URL(statusUrl, base).toString();
        }

        const base = String(apiBaseUrl || '').replace(/\/+$/, '');
        const path = String(statusUrl).replace(/^\/+/, '');
        return base ? `${base}/${path}` : `/${path}`;
    }

    return {
        isUploadQueuedResponse,
        isUploadSuccessResponse,
        getUploadTaskMessage,
        resolveStatusUrl
    };
}));
