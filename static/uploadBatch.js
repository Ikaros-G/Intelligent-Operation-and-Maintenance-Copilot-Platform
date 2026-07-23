(function (root, factory) {
    const api = factory();
    if (typeof module === 'object' && module.exports) {
        module.exports = api;
    }
    root.UploadBatch = api;
}(typeof globalThis !== 'undefined' ? globalThis : this, function () {
    const DEFAULT_MAX_FILES = 10;
    const DEFAULT_MAX_SIZE = 50 * 1024 * 1024;
    const ALLOWED_EXTENSIONS = ['.txt', '.md', '.markdown'];

    function validateSelection(files, options = {}) {
        const list = Array.from(files || []);
        const maxFiles = options.maxFiles || DEFAULT_MAX_FILES;
        const maxSize = options.maxSize || DEFAULT_MAX_SIZE;

        if (list.length > maxFiles) {
            return { accepted: [], rejected: [], tooMany: true, maxFiles };
        }

        const accepted = [];
        const rejected = [];
        list.forEach(file => {
            const name = String(file.name || '').toLowerCase();
            if (!ALLOWED_EXTENSIONS.some(extension => name.endsWith(extension))) {
                rejected.push({ file, reason: 'unsupported_type' });
            } else if (file.size > maxSize) {
                rejected.push({ file, reason: 'file_too_large' });
            } else {
                accepted.push(file);
            }
        });

        return { accepted, rejected, tooMany: false, maxFiles };
    }

    async function runSequentially(items, handler) {
        const results = [];
        for (let index = 0; index < items.length; index += 1) {
            const item = items[index];
            try {
                results.push({ status: 'fulfilled', value: await handler(item, index) });
            } catch (reason) {
                results.push({ status: 'rejected', reason });
            }
        }
        return results;
    }

    function escapeMarkdownHtml(text) {
        return String(text ?? '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;');
    }

    function buildUploadSummary(records) {
        const items = Array.from(records || []);
        if (!items.length) {
            return {
                title: '暂无文件上传结果',
                markdown: '暂无文件上传结果'
            };
        }

        const success = items.filter(item => item.state === 'SUCCESS');
        const failed = items.filter(item => item.state === 'FAILURE');
        const pending = items.filter(item => item.state !== 'SUCCESS' && item.state !== 'FAILURE');
        const firstSuccessName = success[0]?.name || items[0]?.name || '文件';

        const parts = [];
        if (success.length === items.length && success.length === 1) {
            parts.push(`${firstSuccessName} 上传成功`);
        } else if (success.length === items.length) {
            parts.push(`${firstSuccessName} 等 ${success.length} 个文件上传成功`);
        } else if (success.length === 1) {
            parts.push(`${firstSuccessName} 上传成功`);
        } else if (success.length > 1) {
            parts.push(`${firstSuccessName} 等 ${success.length} 个文件上传成功`);
        }
        if (failed.length) parts.push(`${failed.length} 个失败`);
        if (pending.length) parts.push(`${pending.length} 个处理中`);

        const title = parts.length ? parts.join('，') : `${items.length} 个文件正在上传或建立索引`;
        const detailItems = items.map(item => {
            let label = '处理中';
            if (item.state === 'SUCCESS') label = '成功';
            if (item.state === 'FAILURE') label = `失败${item.error ? `，${item.error}` : ''}`;
            return `<li>${escapeMarkdownHtml(item.name)}：${escapeMarkdownHtml(label)}</li>`;
        });

        return {
            title,
            markdown: `${escapeMarkdownHtml(title)}\n\n<details><summary>查看文件明细</summary><ul>${detailItems.join('')}</ul></details>`
        };
    }

    return { validateSelection, runSequentially, buildUploadSummary };
}));
