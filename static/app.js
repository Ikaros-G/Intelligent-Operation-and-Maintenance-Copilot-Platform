// SuperBizAgent 前端应用
class SuperBizAgentApp {
    constructor() {
        // Use the same host that served the page so LAN clients do not call their own localhost.
        this.apiBaseUrl = '/api';
        this.currentMode = 'stream'; // 'quick' 或 'stream'
        this.sessionId = this.generateSessionId();
        this.isStreaming = false;
        this.currentChatHistory = []; // 当前对话的消息历史
        this.currentChatTitle = null;
        this.chatHistories = this.loadChatHistories(); // 所有历史对话
        this.isCurrentChatFromHistory = false; // 标记当前对话是否是从历史记录加载的
        
        this.initializeElements();
        this.bindEvents();
        this.updateUI();
        this.initMarkdown();
        this.checkAndSetCentered();
        this.renderChatHistory();
        setTimeout(() => this.resumeActiveStream(), 0);
    }

    // 初始化Markdown配置
    initMarkdown() {
        // 等待 marked 库加载完成
        const checkMarked = () => {
            if (typeof marked !== 'undefined') {
                try {
                    // 配置marked选项
                    marked.setOptions({
                        breaks: true,  // 支持GFM换行
                        gfm: true,     // 启用GitHub风格的Markdown
                        headerIds: false,
                        mangle: false
                    });

                    // 配置代码高亮
                    if (typeof hljs !== 'undefined') {
                        marked.setOptions({
                            highlight: function(code, lang) {
                                if (lang && hljs.getLanguage(lang)) {
                                    try {
                                        return hljs.highlight(code, { language: lang }).value;
                                    } catch (err) {
                                        console.error('代码高亮失败:', err);
                                    }
                                }
                                return code;
                            }
                        });
                    }
                    console.log('Markdown 渲染库初始化成功');
                } catch (e) {
                    console.error('Markdown 配置失败:', e);
                }
            } else {
                // 如果 marked 还没加载，等待一段时间后重试
                setTimeout(checkMarked, 100);
            }
        };
        checkMarked();
    }

    // 安全地渲染 Markdown
    renderMarkdown(content) {
        if (!content) return '';
        
        // 检查 marked 是否可用
        if (typeof marked === 'undefined') {
            console.warn('marked 库未加载，使用纯文本显示');
            return this.escapeHtml(content);
        }
        
        try {
            const html = marked.parse(content);
            return this.sanitizeRenderedHtml(html);
        } catch (e) {
            console.error('Markdown 渲染失败:', e);
            return this.escapeHtml(content);
        }
    }

    sanitizeRenderedHtml(html) {
        const template = document.createElement('template');
        template.innerHTML = html;

        const blockedTags = [
            'script',
            'iframe',
            'object',
            'embed',
            'link',
            'meta',
            'style',
            'base',
            'form'
        ];
        template.content.querySelectorAll(blockedTags.join(',')).forEach(element => element.remove());

        template.content.querySelectorAll('*').forEach(element => {
            Array.from(element.attributes).forEach(attribute => {
                const name = attribute.name.toLowerCase();
                const value = attribute.value.trim().replace(/[\u0000-\u001F\u007F\s]+/g, '').toLowerCase();
                const isUrlAttribute = ['href', 'src', 'xlink:href', 'formaction'].includes(name);
                const unsafeUrl = isUrlAttribute && /^(javascript|data|vbscript):/.test(value);

                if (name.startsWith('on') || name === 'srcdoc' || unsafeUrl) {
                    element.removeAttribute(attribute.name);
                }
            });

            if (element.tagName.toLowerCase() === 'a' && element.getAttribute('target') === '_blank') {
                element.setAttribute('rel', 'noopener noreferrer');
            }
        });

        return template.innerHTML;
    }

    // 高亮代码块
    highlightCodeBlocks(container) {
        if (typeof hljs !== 'undefined' && container) {
            try {
                container.querySelectorAll('pre code').forEach((block) => {
                    if (!block.classList.contains('hljs')) {
                        hljs.highlightElement(block);
                    }
                });
            } catch (e) {
                console.error('代码高亮失败:', e);
            }
        }
    }

    // 初始化DOM元素
    initializeElements() {
        // 侧边栏元素
        this.sidebar = document.querySelector('.sidebar');
        this.newChatBtn = document.getElementById('newChatBtn');
        this.aiOpsSidebarBtn = document.getElementById('aiOpsSidebarBtn');
        
        // 输入区域元素
        this.messageInput = document.getElementById('messageInput');
        this.sendButton = document.getElementById('sendButton');
        this.toolsBtn = document.getElementById('toolsBtn');
        this.toolsMenu = document.getElementById('toolsMenu');
        this.uploadFileItem = document.getElementById('uploadFileItem');
        this.modeSelectorBtn = document.getElementById('modeSelectorBtn');
        this.modeDropdown = document.getElementById('modeDropdown');
        this.currentModeText = document.getElementById('currentModeText');
        this.fileInput = document.getElementById('fileInput');
        
        // 聊天区域元素
        this.chatMessages = document.getElementById('chatMessages');
        this.loadingOverlay = document.getElementById('loadingOverlay');
        this.chatContainer = document.querySelector('.chat-container');
        this.welcomeGreeting = document.getElementById('welcomeGreeting');
        this.chatHistoryList = document.getElementById('chatHistoryList');
        
        // 初始化时检查是否需要居中
        this.checkAndSetCentered();
    }

    // 绑定事件监听器
    bindEvents() {
        // 新建对话
        if (this.newChatBtn) {
            this.newChatBtn.addEventListener('click', () => this.newChat());
        }
        
        // AI Ops按钮
        if (this.aiOpsSidebarBtn) {
            this.aiOpsSidebarBtn.addEventListener('click', () => this.triggerAIOps());
        }
        
        // 模式选择下拉菜单
        if (this.modeSelectorBtn) {
            this.modeSelectorBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.toggleModeDropdown();
            });
        }
        
        // 下拉菜单项点击
        const dropdownItems = document.querySelectorAll('.dropdown-item');
        dropdownItems.forEach(item => {
            item.addEventListener('click', (e) => {
                const mode = item.getAttribute('data-mode');
                this.selectMode(mode);
                this.closeModeDropdown();
            });
        });
        
        // 点击外部关闭下拉菜单
        document.addEventListener('click', (e) => {
            if (!this.modeSelectorBtn.contains(e.target) && 
                !this.modeDropdown.contains(e.target)) {
                this.closeModeDropdown();
            }
        });
        
        // 发送消息
        if (this.sendButton) {
            this.sendButton.addEventListener('click', () => this.sendMessage());
        }
        
        if (this.messageInput) {
            this.messageInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    this.sendMessage();
                }
            });
        }
        
        // 工具按钮和菜单
        if (this.toolsBtn) {
            this.toolsBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.toggleToolsMenu();
            });
        }
        
        // 工具菜单项点击事件
        if (this.uploadFileItem) {
            this.uploadFileItem.addEventListener('click', () => {
                if (this.fileInput) {
                    this.fileInput.click();
                }
                this.closeToolsMenu();
            });
        }
        
        // 点击外部关闭工具菜单
        document.addEventListener('click', (e) => {
            if (this.toolsBtn && this.toolsMenu && 
                !this.toolsBtn.contains(e.target) && 
                !this.toolsMenu.contains(e.target)) {
                this.closeToolsMenu();
            }
        });
        
        if (this.fileInput) {
            this.fileInput.addEventListener('change', (e) => this.handleFileSelect(e));
        }
    }

    // 切换工具菜单显示/隐藏
    toggleToolsMenu() {
        if (this.toolsMenu && this.toolsBtn) {
            const wrapper = this.toolsBtn.closest('.tools-btn-wrapper');
            if (wrapper) {
                wrapper.classList.toggle('active');
            }
        }
    }

    // 关闭工具菜单
    closeToolsMenu() {
        if (this.toolsMenu && this.toolsBtn) {
            const wrapper = this.toolsBtn.closest('.tools-btn-wrapper');
            if (wrapper) {
                wrapper.classList.remove('active');
            }
        }
    }

    // 新建对话
    newChat() {
        if (this.isStreaming) {
            this.showNotification('请等待当前对话完成后再新建对话', 'warning');
            return;
        }
        
        // 如果当前有对话内容，且不是从历史记录加载的，才保存为新的历史对话
        // 如果是从历史记录加载的，只需要更新该历史记录
        if (this.currentChatHistory.length > 0) {
            if (this.isCurrentChatFromHistory) {
                // 当前对话是从历史记录加载的，更新该历史记录
                this.updateCurrentChatHistory();
            } else {
                // 当前对话是新对话，保存为新的历史对话
                this.saveCurrentChat();
            }
        }
        
        // 停止所有进行中的操作
        this.isStreaming = false;
        
        // 清空输入框
        if (this.messageInput) {
            this.messageInput.value = '';
        }
        
        // 清空当前对话历史
        this.currentChatHistory = [];
        
        // 重置标记
        this.isCurrentChatFromHistory = false;
        this.currentChatTitle = null;
        
        // 清空聊天记录
        if (this.chatMessages) {
            this.chatMessages.innerHTML = '';
        }
        
        // 生成新的会话ID
        this.sessionId = this.generateSessionId();
        
        // 重置模式为流式
        this.currentMode = 'stream';
        this.updateUI();
        
        // 重新设置居中样式（确保对话框居中显示）
        this.checkAndSetCentered();
        
        // 确保容器有过渡动画
        if (this.chatContainer) {
            this.chatContainer.style.transition = 'all 0.5s ease';
        }
        
        // 更新历史对话列表
        this.renderChatHistory();
    }
    
    // 保存当前对话到历史记录（新建）
    saveCurrentChat() {
        if (this.currentChatHistory.length === 0) {
            return;
        }
        
        // 检查是否已存在相同ID的历史记录
        const existingIndex = this.chatHistories.findIndex(h => h.id === this.sessionId);
        if (existingIndex !== -1) {
            // 如果已存在，更新而不是新建
            this.updateCurrentChatHistory();
            return;
        }
        
        // 获取对话标题（使用第一条用户消息的前30个字符）
        const firstUserMessage = this.currentChatHistory.find(msg => msg.type === 'user');
        const title = this.currentChatTitle || (firstUserMessage ? 
            (firstUserMessage.content.substring(0, 30) + (firstUserMessage.content.length > 30 ? '...' : '')) : 
            '新对话');
        
        const chatHistory = {
            id: this.sessionId,
            title: title,
            messages: [...this.currentChatHistory],
            createdAt: new Date().toISOString(),
            updatedAt: new Date().toISOString()
        };
        
        // 添加到历史记录列表的开头
        this.chatHistories.unshift(chatHistory);
        
        // 限制历史记录数量（最多保存50条）
        if (this.chatHistories.length > 50) {
            this.chatHistories = this.chatHistories.slice(0, 50);
        }
        
        // 保存到localStorage
        this.saveChatHistories();
    }
    
    // 更新当前对话的历史记录
    updateCurrentChatHistory() {
        if (this.currentChatHistory.length === 0) {
            return;
        }
        
        const existingIndex = this.chatHistories.findIndex(h => h.id === this.sessionId);
        if (existingIndex === -1) {
            // 如果不存在，调用保存方法
            this.saveCurrentChat();
            return;
        }
        
        // 更新现有的历史记录
        const history = this.chatHistories[existingIndex];
        history.messages = [...this.currentChatHistory];
        history.updatedAt = new Date().toISOString();
        
        // 如果标题需要更新（第一条消息改变了）
        const firstUserMessage = this.currentChatHistory.find(msg => msg.type === 'user');
        if (firstUserMessage) {
            const newTitle = firstUserMessage.content.substring(0, 30) + (firstUserMessage.content.length > 30 ? '...' : '');
            if (history.title !== newTitle) {
                history.title = newTitle;
            }
        }
        
        // 保存到localStorage
        this.saveChatHistories();
    }
    
    // 加载历史对话列表
    loadChatHistories() {
        try {
            const stored = localStorage.getItem('chatHistories');
            return stored ? JSON.parse(stored) : [];
        } catch (e) {
            console.error('加载历史对话失败:', e);
            return [];
        }
    }
    
    // 保存历史对话列表到localStorage
    saveChatHistories() {
        try {
            localStorage.setItem('chatHistories', JSON.stringify(this.chatHistories));
        } catch (e) {
            console.error('保存历史对话失败:', e);
        }
    }

    loadActiveStream() {
        try {
            const stored = localStorage.getItem('activeSseStream');
            const active = stored ? JSON.parse(stored) : null;
            return active && active.streamId && active.status === 'running' ? active : null;
        } catch (error) {
            console.error('加载未完成流失败:', error);
            return null;
        }
    }

    saveActiveStream(active) {
        active.updatedAt = new Date().toISOString();
        localStorage.setItem('activeSseStream', JSON.stringify(active));
    }

    clearActiveStream(streamId) {
        const active = this.loadActiveStream();
        if (!active || active.streamId === streamId) {
            localStorage.removeItem('activeSseStream');
        }
    }

    persistActiveStream(active) {
        this.saveActiveStream(active);
        const message = {
            type: 'assistant',
            content: active.content || '',
            timestamp: active.startedAt || new Date().toISOString(),
            streamId: active.streamId,
            streamKind: active.kind,
            streamStatus: active.status,
            lastEventId: active.cursor || '0-0'
        };
        if (active.aiopsState) message.aiopsState = { ...active.aiopsState };

        const existingIndex = this.currentChatHistory.findIndex(item => item.streamId === active.streamId);
        if (existingIndex === -1) this.currentChatHistory.push(message);
        else this.currentChatHistory[existingIndex] = message;
        this.saveCurrentChat();
    }

    renderStreamContent(messageElement, content, kind) {
        if (!messageElement) return;
        if (kind === 'aiops') messageElement.classList.add('aiops-message');
        const messageContent = messageElement.querySelector('.message-content');
        if (!messageContent) return;
        messageContent.classList.remove('loading-message-content');
        messageContent.innerHTML = this.renderMarkdown(content || '');
        this.highlightCodeBlocks(messageContent);
        this.scrollToBottom();
    }

    restoreActiveSession(active) {
        const history = this.chatHistories.find(item => item.id === active.sessionId);
        this.sessionId = active.sessionId;
        this.currentChatTitle = active.title || (history && history.title) || null;
        this.isCurrentChatFromHistory = Boolean(history);
        this.currentChatHistory = window.ChatHistory.normalizeMessages(history ? history.messages : []);

        let activeElement = null;
        if (this.chatMessages) {
            this.chatMessages.innerHTML = '';
            this.currentChatHistory.forEach(message => {
                const isActive = message.streamId === active.streamId;
                const element = this.addMessage(message.type, message.content, isActive, false);
                if (isActive) activeElement = element;
            });
        }
        if (!activeElement) {
            activeElement = this.addMessage('assistant', active.content || '', true, false);
        }
        this.renderStreamContent(activeElement, active.content, active.kind);
        this.checkAndSetCentered();
        return activeElement;
    }

    async resumeActiveStream() {
        const active = this.loadActiveStream();
        if (!active || this.isStreaming) return;

        const messageElement = this.restoreActiveSession(active);
        this.isStreaming = true;
        this.updateUI();
        this.showNotification('检测到未完成输出，正在继续接收...', 'info');
        try {
            await this.consumeResumableStream(active, messageElement);
        } catch (error) {
            console.error('恢复流式输出失败:', error);
            active.status = 'failed';
            active.error = error.message;
            this.persistActiveStream(active);
            this.finishResumableStream(active, messageElement);
        } finally {
            this.isStreaming = false;
            this.updateUI();
        }
    }
    
    // 渲染历史对话列表
    renderChatHistory() {
        if (!this.chatHistoryList) {
            return;
        }
        
        this.chatHistoryList.innerHTML = '';
        
        if (this.chatHistories.length === 0) {
            return;
        }
        
        this.chatHistories.forEach((history, index) => {
            const historyItem = document.createElement('div');
            historyItem.className = 'history-item';
            historyItem.dataset.historyId = history.id;
            
            historyItem.innerHTML = `
                <div class="history-item-content">
                    <span class="history-item-title">${this.escapeHtml(history.title)}</span>
                </div>
                <button class="history-item-delete" data-history-id="${history.id}" title="删除">
                    <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                        <path d="M18 6L6 18M6 6L18 18" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
                    </svg>
                </button>
            `;
            
            // 点击历史项加载对话
            historyItem.addEventListener('click', (e) => {
                if (!e.target.closest('.history-item-delete')) {
                    this.loadChatHistory(history.id);
                }
            });
            
            // 删除历史对话
            const deleteBtn = historyItem.querySelector('.history-item-delete');
            deleteBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.deleteChatHistory(history.id);
            });
            
            this.chatHistoryList.appendChild(historyItem);
        });
    }
    
    // 加载历史对话
    async loadChatHistory(historyId) {
        const history = this.chatHistories.find(h => h.id === historyId);
        if (!history) {
            return;
        }
        
        // 如果当前有对话内容，且不是同一个对话，先保存
        if (this.currentChatHistory.length > 0 && this.sessionId !== historyId) {
            if (this.isCurrentChatFromHistory) {
                // 如果当前对话也是从历史记录加载的，更新它
                this.updateCurrentChatHistory();
            } else {
                // 如果当前对话是新对话，保存为新历史
                this.saveCurrentChat();
            }
        }
        
        try {
            // 从后端获取会话历史
            const response = await fetch(`/api/chat/session/${historyId}`);
            if (response.ok) {
                const data = await response.json();
                const backendHistory = data.history || [];
                
                // 更新会话ID
                this.sessionId = history.id;
                this.currentChatTitle = history.title;
                this.isCurrentChatFromHistory = true;
                
                // 清空并重新渲染消息
                if (this.chatMessages) {
                    this.chatMessages.innerHTML = '';
                    
                    // 如果后端有历史记录，使用后端的
                    if (backendHistory.length > 0) {
                        const normalizedMessages = window.ChatHistory.normalizeMessages(backendHistory);
                        this.currentChatHistory = [...normalizedMessages];
                        normalizedMessages.forEach(msg => {
                            this.addMessage(msg.type, msg.content, false, false);
                        });
                    } else {
                        // 否则使用localStorage的历史记录
                        const normalizedMessages = window.ChatHistory.normalizeMessages(history.messages);
                        this.currentChatHistory = [...normalizedMessages];
                        normalizedMessages.forEach(msg => {
                            this.addMessage(msg.type, msg.content, false, false);
                        });
                    }
                }
            } else {
                // 如果后端请求失败，使用localStorage的历史记录
                console.warn('从后端加载历史失败，使用本地缓存');
                this.sessionId = history.id;
                this.currentChatTitle = history.title;
                const normalizedMessages = window.ChatHistory.normalizeMessages(history.messages);
                this.currentChatHistory = [...normalizedMessages];
                this.isCurrentChatFromHistory = true;
                
                if (this.chatMessages) {
                    this.chatMessages.innerHTML = '';
                    normalizedMessages.forEach(msg => {
                        this.addMessage(msg.type, msg.content, false, false);
                    });
                }
            }
        } catch (error) {
            console.error('加载会话历史失败:', error);
            // 出错时使用localStorage的历史记录
            this.sessionId = history.id;
            this.currentChatTitle = history.title;
            const normalizedMessages = window.ChatHistory.normalizeMessages(history.messages);
            this.currentChatHistory = [...normalizedMessages];
            this.isCurrentChatFromHistory = true;
            
            if (this.chatMessages) {
                this.chatMessages.innerHTML = '';
                normalizedMessages.forEach(msg => {
                    this.addMessage(msg.type, msg.content, false, false);
                });
            }
        }
        
        // 更新UI
        this.checkAndSetCentered();
        this.renderChatHistory();
    }
    
    // 删除历史对话
    async deleteChatHistory(historyId) {
        try {
            // 调用后端API清空会话
            const response = await fetch('/api/chat/clear', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    session_id: historyId
                })
            });

            if (!response.ok) {
                throw new Error('清空会话失败');
            }

            const result = await response.json();
            
            if (result.status === 'success') {
                // 从本地存储中删除
                this.chatHistories = this.chatHistories.filter(h => h.id !== historyId);
                this.saveChatHistories();
                this.renderChatHistory();
                
                // 如果删除的是当前对话，清空当前对话
                if (this.sessionId === historyId) {
                    this.currentChatHistory = [];
                    if (this.chatMessages) {
                        this.chatMessages.innerHTML = '';
                    }
                    this.sessionId = this.generateSessionId();
                    this.currentChatTitle = null;
                    this.checkAndSetCentered();
                }
                
                this.showNotification('会话已清空', 'success');
            } else {
                throw new Error(result.message || '清空会话失败');
            }
        } catch (error) {
            console.error('删除历史对话失败:', error);
            this.showNotification('删除失败: ' + error.message, 'error');
        }
    }

    // 切换模式下拉菜单
    toggleModeDropdown() {
        if (this.modeSelectorBtn && this.modeDropdown) {
            const wrapper = this.modeSelectorBtn.closest('.mode-selector-wrapper');
            if (wrapper) {
                wrapper.classList.toggle('active');
            }
        }
    }

    // 关闭模式下拉菜单
    closeModeDropdown() {
        if (this.modeSelectorBtn && this.modeDropdown) {
            const wrapper = this.modeSelectorBtn.closest('.mode-selector-wrapper');
            if (wrapper) {
                wrapper.classList.remove('active');
            }
        }
    }

    // 选择模式
    selectMode(mode) {
        if (this.isStreaming) {
            this.showNotification('请等待当前对话完成后再切换模式', 'warning');
            return;
        }
        
        this.currentMode = mode;
        this.updateUI();
        
        const modeNames = {
            'quick': '快速',
            'stream': '流式'
        };
        
        this.showNotification(`已切换到${modeNames[mode]}模式`, 'info');
    }

    // 更新UI
    updateUI() {
        // 更新模式选择器显示
        if (this.currentModeText) {
            const modeNames = {
                'quick': '快速',
                'stream': '流式'
            };
            this.currentModeText.textContent = modeNames[this.currentMode] || '快速';
        }
        
        // 更新下拉菜单选中状态
        const dropdownItems = document.querySelectorAll('.dropdown-item');
        dropdownItems.forEach(item => {
            const mode = item.getAttribute('data-mode');
            if (mode === this.currentMode) {
                item.classList.add('active');
            } else {
                item.classList.remove('active');
            }
        });
        
        // 更新发送按钮状态
        if (this.sendButton) {
            this.sendButton.disabled = this.isStreaming;
        }
        
        // 更新输入框状态
        if (this.messageInput) {
            this.messageInput.disabled = this.isStreaming;
            this.messageInput.placeholder = '问问运维Copilot助手';
        }
    }

    // 生成随机会话ID
    generateSessionId() {
        return 'session_' + Math.random().toString(36).substr(2, 9) + '_' + Date.now();
    }

    // 发送消息
    async sendMessage() {
        let message = '';
        if (this.messageInput) {
            message = this.messageInput.value.trim();
        }
        
        if (!message) {
            this.showNotification('请输入消息内容', 'warning');
            return;
        }

        if (this.isStreaming) {
            this.showNotification('请等待当前对话完成', 'warning');
            return;
        }

        // 显示用户消息
        this.addMessage('user', message);
        this.saveCurrentChat();
        this.renderChatHistory();
        
        // 清空输入框
        if (this.messageInput) {
            this.messageInput.value = '';
        }

        // 设置发送状态
        this.isStreaming = true;
        this.updateUI();

        try {
            if (this.currentMode === 'quick') {
                await this.sendQuickMessage(message);
            } else if (this.currentMode === 'stream') {
                await this.sendStreamMessage(message);
            }
        } catch (error) {
            console.error('发送消息失败:', error);
            this.addMessage('assistant', '抱歉，发送消息时出现错误：' + error.message);
        } finally {
            this.isStreaming = false;
            this.updateUI();
            
            // 如果当前对话是从历史记录加载的，更新历史记录
            if (this.isCurrentChatFromHistory && this.currentChatHistory.length > 0) {
                this.updateCurrentChatHistory();
                this.renderChatHistory(); // 更新历史对话列表显示
            }
        }
    }

    // 发送快速消息（普通对话）
    async sendQuickMessage(message) {
        // 添加等待提示消息
        const loadingMessage = this.addLoadingMessage('正在思考...');
        
        try {
            const response = await fetch(`${this.apiBaseUrl}/chat`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    Id: this.sessionId,
                    Question: message
                })
            });

            if (!response.ok) {
                throw new Error(`HTTP错误: ${response.status}`);
            }

            const data = await response.json();
            console.log('[sendQuickMessage] 响应数据:', JSON.stringify(data));
            
            // 移除等待提示消息
            if (loadingMessage && loadingMessage.parentNode) {
                loadingMessage.parentNode.removeChild(loadingMessage);
            }
            
            // 统一响应格式：检查 data.code 或 data.message 判断请求是否成功
            if (data.code === 200 || data.message === 'success') {
                // data.data 是 ChatResponse 对象
                const chatResponse = data.data;
                
                if (chatResponse && chatResponse.success) {
                    // 成功：添加实际响应消息（即使 answer 为空也显示）
                    const answer = chatResponse.answer || '（无回复内容）';
                    this.addMessage('assistant', answer);
                } else if (chatResponse && chatResponse.errorMessage) {
                    // 业务错误
                    throw new Error(chatResponse.errorMessage);
                } else {
                    // 兜底：尝试显示任何可用内容
                    const fallbackAnswer = chatResponse?.answer || chatResponse?.errorMessage || '服务返回了空内容';
                    this.addMessage('assistant', fallbackAnswer);
                }
            } else {
                // HTTP 成功但业务失败
                throw new Error(data.message || '请求失败');
            }
        } catch (error) {
            // 出错时也要移除等待提示消息
            if (loadingMessage && loadingMessage.parentNode) {
                loadingMessage.parentNode.removeChild(loadingMessage);
            }
            throw error;
        }
    }

    // 发送流式消息
    async sendStreamMessage(message) {
        const response = await fetch(`${this.apiBaseUrl}/chat_stream`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ Id: this.sessionId, Question: message })
        });
        if (!response.ok) throw new Error(`HTTP错误: ${response.status}`);

        const streamId = response.headers.get('X-Stream-ID');
        if (!streamId) throw new Error('服务端未返回可恢复流标识');
        const active = {
            streamId,
            sessionId: this.sessionId,
            title: this.currentChatTitle,
            kind: 'chat',
            cursor: '0-0',
            content: '',
            status: 'running',
            startedAt: new Date().toISOString()
        };
        const assistantMessageElement = this.addMessage('assistant', '', true, false);
        this.persistActiveStream(active);
        this.renderChatHistory();
        await this.consumeResumableStream(active, assistantMessageElement, response);
    }

    processResumableEvent(active, messageElement, envelope) {
        if (envelope.id) active.cursor = envelope.id;
        const event = envelope.data || {};
        if (!event || typeof event !== 'object') return;

        if (active.kind === 'chat') {
            if (event.type === 'content') {
                active.content += event.data || '';
            } else if (event.type === 'done' || event.type === 'complete') {
                if (!active.content && event.data && event.data.answer) active.content = event.data.answer;
                active.status = 'completed';
            } else if (event.type === 'error') {
                active.status = 'failed';
                active.error = event.data || event.message || '流式回答失败';
            }
        } else {
            const previousState = active.aiopsState || window.AIOpsStream.createState();
            active.aiopsState = window.AIOpsStream.applyEvent(previousState, event);
            active.content = active.aiopsState.content;
            if (active.aiopsState.done) active.status = 'completed';
            if (active.aiopsState.error) {
                active.status = 'failed';
                active.error = active.aiopsState.error;
            }
        }

        this.persistActiveStream(active);
        this.renderStreamContent(messageElement, active.content, active.kind);
    }

    async consumeResumableStream(active, messageElement, initialResponse = null) {
        let response = initialResponse;
        let retryAttempt = 0;
        let reconnectNoticeShown = false;

        while (active.status === 'running') {
            try {
                if (!response) {
                    const cursor = encodeURIComponent(active.cursor || '0-0');
                    response = await fetch(`${this.apiBaseUrl}/streams/${active.streamId}?after=${cursor}`);
                    if (response.status === 404) throw new Error('流任务不存在或已过期');
                    if (!response.ok) throw new Error(`恢复流失败: HTTP ${response.status}`);
                }
                await window.ResumableStream.readResponse(response, envelope => {
                    this.processResumableEvent(active, messageElement, envelope);
                });
                response = null;
                retryAttempt = 0;
            } catch (error) {
                response = null;
                if (error.message.includes('不存在或已过期')) {
                    active.status = 'failed';
                    active.error = error.message;
                    break;
                }
                retryAttempt += 1;
                if (!reconnectNoticeShown) {
                    this.showNotification('连接中断，正在恢复输出...', 'info');
                    reconnectNoticeShown = true;
                }
                await new Promise(resolve => setTimeout(resolve, Math.min(5000, retryAttempt * 1000)));
            }
        }
        this.persistActiveStream(active);
        this.finishResumableStream(active, messageElement);
    }

    finishResumableStream(active, messageElement) {
        if (active.status === 'failed' && !active.content) {
            active.content = `错误：${active.error || '任务执行失败'}`;
            this.persistActiveStream(active);
        }
        if (messageElement) messageElement.classList.remove('streaming');
        this.renderStreamContent(messageElement, active.content, active.kind);
        this.clearActiveStream(active.streamId);
        this.saveCurrentChat();
        this.renderChatHistory();
        if (active.status === 'failed') {
            this.showNotification(active.error || '流式任务执行失败', 'error');
        }
    }

    // 添加消息到聊天界面
    addMessage(type, content, isStreaming = false, saveToHistory = true) {
        // 检查是否是第一条消息，如果是则移除居中样式
        const isFirstMessage = this.chatMessages && this.chatMessages.querySelectorAll('.message').length === 0;
        
        // 保存消息到当前对话历史（如果不是流式消息且需要保存）
        if (!isStreaming && saveToHistory && content) {
            this.currentChatHistory.push({
                type: type,
                content: content,
                timestamp: new Date().toISOString()
            });
        }
        
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${type}${isStreaming ? ' streaming' : ''}`;

        // 如果是assistant消息，添加头像图标
        if (type === 'assistant') {
            const messageAvatar = document.createElement('div');
            messageAvatar.className = 'message-avatar';
            messageAvatar.innerHTML = `
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M12 2L15.09 8.26L22 9.27L17 14.14L18.18 21.02L12 17.77L5.82 21.02L7 14.14L2 9.27L8.91 8.26L12 2Z" fill="white"/>
                </svg>
            `;
            messageDiv.appendChild(messageAvatar);
        }

        // 创建消息内容包装器
        const messageContentWrapper = document.createElement('div');
        messageContentWrapper.className = 'message-content-wrapper';

        const messageContent = document.createElement('div');
        messageContent.className = 'message-content';
        
        // 如果是assistant消息且不是流式消息，使用Markdown渲染
        if (type === 'assistant' && !isStreaming) {
            messageContent.innerHTML = this.renderMarkdown(content);
            // 高亮代码块
            this.highlightCodeBlocks(messageContent);
        } else {
            // 用户消息或流式消息使用纯文本
            messageContent.textContent = content;
        }

        messageContentWrapper.appendChild(messageContent);
        messageDiv.appendChild(messageContentWrapper);

        if (this.chatMessages) {
            this.chatMessages.appendChild(messageDiv);
            
            // 如果是第一条消息，移除居中样式并添加动画
            if (isFirstMessage && this.chatContainer) {
                this.chatContainer.classList.remove('centered');
                // 添加动画类
                this.chatContainer.style.transition = 'all 0.5s ease';
            }
            
            this.scrollToBottom();
        }

        return messageDiv;
    }

    // 添加带加载动画的消息
    addLoadingMessage(content) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message assistant';

        // 添加头像图标
        const messageAvatar = document.createElement('div');
        messageAvatar.className = 'message-avatar';
        messageAvatar.innerHTML = `
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M12 2L15.09 8.26L22 9.27L17 14.14L18.18 21.02L12 17.77L5.82 21.02L7 14.14L2 9.27L8.91 8.26L12 2Z" fill="white"/>
            </svg>
        `;
        messageDiv.appendChild(messageAvatar);

        // 创建消息内容包装器
        const messageContentWrapper = document.createElement('div');
        messageContentWrapper.className = 'message-content-wrapper';

        const messageContent = document.createElement('div');
        messageContent.className = 'message-content loading-message-content';
        
        // 创建文本和动画容器
        const textSpan = document.createElement('span');
        textSpan.textContent = content;
        
        // 创建旋转动画图标
        const loadingIcon = document.createElement('span');
        loadingIcon.className = 'loading-spinner-icon';
        loadingIcon.innerHTML = `
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8z" fill="currentColor" opacity="0.2"/>
                <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10c1.54 0 3-.36 4.28-1l-1.5-2.6C13.64 19.62 12.84 20 12 20c-4.41 0-8-3.59-8-8s3.59-8 8-8c.84 0 1.64.38 2.18 1l1.5-2.6C13 2.36 12.54 2 12 2z" fill="currentColor"/>
            </svg>
        `;
        
        messageContent.appendChild(textSpan);
        messageContent.appendChild(loadingIcon);
        messageContentWrapper.appendChild(messageContent);
        messageDiv.appendChild(messageContentWrapper);

        if (this.chatMessages) {
            this.chatMessages.appendChild(messageDiv);
            
            // 如果是第一条消息，移除居中样式
            const isFirstMessage = this.chatMessages.querySelectorAll('.message').length === 1;
            if (isFirstMessage && this.chatContainer) {
                this.chatContainer.classList.remove('centered');
                this.chatContainer.style.transition = 'all 0.5s ease';
            }
            
            this.scrollToBottom();
        }

        return messageDiv;
    }
    
    // 检查并设置居中样式
    checkAndSetCentered() {
        if (this.chatMessages && this.chatContainer) {
            const hasMessages = this.chatMessages.querySelectorAll('.message').length > 0;
            if (!hasMessages) {
                this.chatContainer.classList.add('centered');
            } else {
                this.chatContainer.classList.remove('centered');
            }
        }
    }

    // 滚动到底部
    scrollToBottom() {
        if (this.chatMessages) {
            this.chatMessages.scrollTop = this.chatMessages.scrollHeight;
        }
    }

    // 处理流式传输完成
    handleStreamComplete(assistantMessageElement, fullResponse) {
        if (assistantMessageElement) {
            assistantMessageElement.classList.remove('streaming');
            const messageContent = assistantMessageElement.querySelector('.message-content');
            if (messageContent) {
                messageContent.innerHTML = this.renderMarkdown(fullResponse);
                // 高亮代码块
                this.highlightCodeBlocks(messageContent);
            }
        }
        // 保存流式消息到历史记录
        if (fullResponse) {
            this.currentChatHistory.push({
                type: 'assistant',
                content: fullResponse,
                timestamp: new Date().toISOString()
            });
            // 如果当前对话是从历史记录加载的，更新历史记录
            if (this.isCurrentChatFromHistory) {
                this.updateCurrentChatHistory();
                this.renderChatHistory();
            }
        }
    }

    // 显示通知
    showNotification(message, type = 'info') {
        // 创建通知元素
        const notification = document.createElement('div');
        notification.className = `notification ${type}`;
        notification.textContent = message;
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 15px 20px;
            border-radius: 8px;
            color: white;
            font-weight: 500;
            z-index: 10000;
            animation: slideIn 0.3s ease;
            max-width: 300px;
        `;

        // 根据类型设置颜色（Google Material Design配色）
        const colors = {
            info: '#1a73e8',
            success: '#34a853',
            warning: '#fbbc04',
            error: '#ea4335'
        };
        notification.style.backgroundColor = colors[type] || colors.info;

        // 添加到页面
        document.body.appendChild(notification);

        // 3秒后自动移除
        setTimeout(() => {
            notification.style.animation = 'slideOut 0.3s ease';
            setTimeout(() => {
                if (notification.parentNode) {
                    notification.parentNode.removeChild(notification);
                }
            }, 300);
        }, 3000);
    }

    // 处理文件选择
    handleFileSelect(event) {
        const selection = window.UploadBatch.validateSelection(event.target.files);
        if (selection.tooMany) {
            this.showNotification(`一次最多上传 ${selection.maxFiles} 个文件`, 'error');
            this.fileInput.value = '';
            return;
        }

        selection.rejected.forEach(({ file, reason }) => {
            const message = reason === 'file_too_large'
                ? `${file.name} 文件大小超过 50MB`
                : `${file.name} 不是支持的 TXT 或 Markdown 文件`;
            this.showNotification(message, 'error');
        });

        if (selection.accepted.length > 0) {
            this.uploadFiles(selection.accepted);
        } else if (this.fileInput) {
            this.fileInput.value = '';
        }
    }

    // 验证文件类型
    validateFileType(file) {
        const fileName = file.name.toLowerCase();
        const allowedExtensions = ['.txt', '.md', '.markdown'];
        return allowedExtensions.some(ext => fileName.endsWith(ext));
    }

    async uploadFiles(files) {
        this.isStreaming = true;
        this.updateUI();
        const uploadRecords = Array.from(files || []).map(file => ({
            name: file.name,
            state: 'PENDING'
        }));
        const summaryMessageElement = this.addMessage('assistant', '', false, false);
        this.updateUploadSummaryMessage(summaryMessageElement, uploadRecords);

        try {
            await window.UploadBatch.runSequentially(files, async (file, index) => {
                this.showUploadOverlay(true, file.name);
                const status = await this.uploadFile(file);
                uploadRecords[index] = {
                    name: file.name,
                    state: status?.state || 'PENDING',
                    error: status?.error
                };
                this.updateUploadSummaryMessage(summaryMessageElement, uploadRecords);
                return status;
            });
        } finally {
            if (this.fileInput) {
                this.fileInput.value = '';
            }
            this.isStreaming = false;
            this.showUploadOverlay(false);
            this.updateUI();
        }
    }

    buildLocalUploadSummary(records) {
        const items = Array.from(records || []);
        if (!items.length) {
            return {
                title: '暂无文件上传结果',
                markdown: '暂无文件上传结果',
                details: []
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
        const details = items.map(item => {
            let label = '处理中';
            if (item.state === 'SUCCESS') label = '成功';
            if (item.state === 'FAILURE') label = `失败${item.error ? `，${item.error}` : ''}`;
            return { name: item.name, label };
        });
        const detailItems = details.map(item => `<li>${this.escapeHtml(item.name)}：${this.escapeHtml(item.label)}</li>`);

        return {
            title,
            markdown: `${this.escapeHtml(title)}\n\n<details><summary>查看文件明细</summary><ul>${detailItems.join('')}</ul></details>`,
            details
        };
    }

    buildUploadSummary(records) {
        const localSummary = this.buildLocalUploadSummary(records);
        if (!window.UploadBatch?.buildUploadSummary) return localSummary;

        try {
            const sharedSummary = window.UploadBatch.buildUploadSummary(records);
            return {
                ...localSummary,
                title: sharedSummary?.title || localSummary.title,
                markdown: sharedSummary?.markdown || localSummary.markdown
            };
        } catch (error) {
            console.warn('上传汇总生成失败，使用本地兜底:', error);
            return localSummary;
        }
    }

    renderUploadSummaryContent(messageElement, summary) {
        if (!messageElement) return;
        let messageContent = messageElement.matches?.('.message-content')
            ? messageElement
            : messageElement.querySelector('.message-content');

        if (!messageContent) {
            const wrapper = messageElement.querySelector?.('.message-content-wrapper');
            if (!wrapper) return;
            messageContent = document.createElement('div');
            messageContent.className = 'message-content';
            wrapper.appendChild(messageContent);
        }

        messageContent.classList.remove('loading-message-content');
        messageContent.textContent = '';

        const titleElement = document.createElement('div');
        titleElement.className = 'upload-summary-title';
        titleElement.textContent = summary.title;
        messageContent.appendChild(titleElement);

        if (summary.details.length > 0) {
            const detailsElement = document.createElement('details');
            const summaryElement = document.createElement('summary');
            summaryElement.textContent = '查看文件明细';
            detailsElement.appendChild(summaryElement);

            const listElement = document.createElement('ul');
            summary.details.forEach(item => {
                const listItem = document.createElement('li');
                listItem.textContent = `${item.name}：${item.label}`;
                listElement.appendChild(listItem);
            });
            detailsElement.appendChild(listElement);
            messageContent.appendChild(detailsElement);
        }

        this.scrollToBottom();
    }

    updateUploadSummaryMessage(messageElement, records) {
        if (!messageElement) return;
        if (!messageElement.dataset.uploadSummaryId) {
            messageElement.dataset.uploadSummaryId = `upload-${Date.now()}-${Math.random().toString(36).slice(2)}`;
        }

        const summary = this.buildUploadSummary(records);
        this.renderUploadSummaryContent(messageElement, summary);

        const message = {
            type: 'assistant',
            content: summary.markdown,
            timestamp: messageElement.dataset.uploadStartedAt || new Date().toISOString(),
            uploadSummaryId: messageElement.dataset.uploadSummaryId
        };
        messageElement.dataset.uploadStartedAt = message.timestamp;

        const existingIndex = this.currentChatHistory.findIndex(
            item => item.uploadSummaryId === message.uploadSummaryId
        );
        if (existingIndex === -1) this.currentChatHistory.push(message);
        else this.currentChatHistory[existingIndex] = message;

        this.saveCurrentChat();
    }

    // 上传单个文件到知识库
    async uploadFile(file) {
        // 再次验证文件类型（双重保险）
        if (!this.validateFileType(file)) {
            this.showNotification('只支持上传 TXT 或 Markdown (.md) 格式的文件', 'error');
            return;
        }

        // 验证文件大小（限制为50MB）
        const maxSize = 50 * 1024 * 1024;
        if (file.size > maxSize) {
            this.showNotification('文件大小不能超过50MB', 'error');
            return;
        }

        try {
            // 创建 FormData
            const formData = new FormData();
            formData.append('file', file);

            // 发送上传请求
            const response = await fetch(`${this.apiBaseUrl}/upload`, {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                throw new Error(`HTTP错误: ${response.status}`);
            }

            const data = await response.json();

            if (window.UploadResponse?.isUploadSuccessResponse(data)) {
                const queued = window.UploadResponse.isUploadQueuedResponse(data);
                if (queued) {
                    this.showUploadOverlay(true, file.name, 'indexing');
                    return await this.pollUploadTask(file.name, data.status_url);
                }
                return { state: 'SUCCESS' };
            } else {
                throw new Error(data.message || '上传失败');
            }
        } catch (error) {
            console.error('文件上传失败:', error);
            this.showNotification('文件上传失败: ' + error.message, 'error');
            return { state: 'FAILURE', error: error.message };
        }
    }

    async pollUploadTask(fileName, statusUrl) {
        for (let attempt = 0; attempt < 30; attempt++) {
            await new Promise(resolve => setTimeout(resolve, 2000));
            try {
                const taskUrl = window.UploadResponse.resolveStatusUrl(this.apiBaseUrl, statusUrl);
                const response = await fetch(taskUrl);
                if (!response.ok) {
                    throw new Error(`HTTP错误: ${response.status}`);
                }
                const status = await response.json();
                if (status.state === 'SUCCESS' || status.state === 'FAILURE') {
                    return status;
                }
            } catch (error) {
                console.error('查询知识库索引状态失败:', error);
            }
        }

        return { state: 'PENDING' };
    }

    // 格式化文件大小
    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
    }

    // 发送智能运维请求（SSE 流式模式）
    async sendAIOpsRequest(loadingMessageElement) {
        const response = await fetch(`${this.apiBaseUrl}/aiops`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_id: this.sessionId })
        });

        if (!response.ok) {
            throw new Error(`HTTP错误: ${response.status}`);
        }

        const streamId = response.headers.get('X-Stream-ID');
        if (!streamId) throw new Error('服务端未返回可恢复流标识');
        const aiopsState = window.AIOpsStream.createState();
        const active = {
            streamId,
            sessionId: this.sessionId,
            title: this.currentChatTitle,
            kind: 'aiops',
            cursor: '0-0',
            content: '',
            status: 'running',
            aiopsState,
            startedAt: new Date().toISOString()
        };
        this.persistActiveStream(active);
        this.renderChatHistory();
        await this.consumeResumableStream(active, loadingMessageElement, response);
    }

    // 更新智能运维流式内容（实时显示）
    updateAIOpsStreamContent(messageElement, content) {
        if (!messageElement) return;
        
        // 添加 aiops-message 类
        messageElement.classList.add('aiops-message');
        
        const messageContentWrapper = messageElement.querySelector('.message-content-wrapper');
        if (messageContentWrapper) {
            let messageContent = messageContentWrapper.querySelector('.message-content');
            if (!messageContent) {
                messageContent = document.createElement('div');
                messageContent.className = 'message-content';
                messageContentWrapper.appendChild(messageContent);
            }
            messageContent.classList.remove('loading-message-content');
            messageContent.innerHTML = this.renderMarkdown(content);
            this.highlightCodeBlocks(messageContent);
            this.scrollToBottom();
        }
    }

    // 更新智能运维消息（带折叠详情）
    updateAIOpsMessage(messageElement, response, details) {
        console.log('updateAIOpsMessage 被调用');
        console.log('messageElement:', messageElement);
        console.log('response:', response);
        console.log('response length:', response ? response.length : 0);
        console.log('details:', details);
        
        if (!messageElement) {
            // 如果没有传入消息元素，则创建新消息
            console.log('messageElement 为空，创建新消息');
            return this.addAIOpsMessage(response, details);
        }

        // 添加aiops-message类
        messageElement.classList.add('aiops-message');

        // 获取消息内容包装器
        const messageContentWrapper = messageElement.querySelector('.message-content-wrapper');
        if (!messageContentWrapper) {
            console.error('未找到 message-content-wrapper');
            return;
        }

        // 清空现有内容（保留消息内容容器）
        const messageContent = messageContentWrapper.querySelector('.message-content');
        if (!messageContent) {
            console.error('未找到 message-content');
            return;
        }

        // 移除加载动画相关的类和内容
        messageContent.classList.remove('loading-message-content');
        messageContent.textContent = '';
        
        // 移除加载图标（如果存在）
        const loadingIcon = messageContent.querySelector('.loading-spinner-icon');
        if (loadingIcon) {
            loadingIcon.remove();
        }

        // 详情部分（可折叠）- 先显示
        if (details && details.length > 0) {
            // 检查是否已存在详情容器
            let detailsContainer = messageElement.querySelector('.aiops-details');
            if (!detailsContainer) {
                detailsContainer = document.createElement('div');
                detailsContainer.className = 'aiops-details';
                messageContentWrapper.insertBefore(detailsContainer, messageContent);
            } else {
                // 清空现有详情
                detailsContainer.innerHTML = '';
            }

            const detailsToggle = document.createElement('div');
            detailsToggle.className = 'details-toggle';
            detailsToggle.innerHTML = `
                <svg class="toggle-icon" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M9 18L15 12L9 6" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
                <span>查看详细步骤 (${details.length}条)</span>
            `;

            const detailsContent = document.createElement('div');
            detailsContent.className = 'details-content';
            
            details.forEach((detail, index) => {
                const detailItem = document.createElement('div');
                detailItem.className = 'detail-item';
                detailItem.innerHTML = `<strong>步骤 ${index + 1}:</strong> ${this.escapeHtml(detail)}`;
                detailsContent.appendChild(detailItem);
            });

            // 点击切换折叠状态
            detailsToggle.addEventListener('click', () => {
                detailsContent.classList.toggle('expanded');
                detailsToggle.classList.toggle('expanded');
            });

            detailsContainer.appendChild(detailsToggle);
            detailsContainer.appendChild(detailsContent);
        }

        // 更新主要响应内容（使用Markdown渲染）
        console.log('开始渲染 Markdown');
        const renderedHtml = this.renderMarkdown(response);
        console.log('Markdown 渲染完成，HTML 长度:', renderedHtml ? renderedHtml.length : 0);
        messageContent.innerHTML = renderedHtml;
        console.log('innerHTML 已设置');
        // 高亮代码块
        this.highlightCodeBlocks(messageContent);
        console.log('代码块高亮完成');
        
        // 保存到历史记录
        this.currentChatHistory.push({
            type: 'assistant',
            content: response,
            timestamp: new Date().toISOString()
        });
        this.saveCurrentChat();
        this.renderChatHistory();
        
        this.scrollToBottom();
        return messageElement;
    }

    // 添加智能运维消息（带折叠详情）- 保留用于兼容性
    addAIOpsMessage(response, details) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message assistant aiops-message';

        // 添加头像图标
        const messageAvatar = document.createElement('div');
        messageAvatar.className = 'message-avatar';
        messageAvatar.innerHTML = `
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M12 2L15.09 8.26L22 9.27L17 14.14L18.18 21.02L12 17.77L5.82 21.02L7 14.14L2 9.27L8.91 8.26L12 2Z" fill="white"/>
            </svg>
        `;
        messageDiv.appendChild(messageAvatar);

        // 创建消息内容包装器
        const messageContentWrapper = document.createElement('div');
        messageContentWrapper.className = 'message-content-wrapper';

        // 详情部分（可折叠）- 先显示
        if (details && details.length > 0) {
            const detailsContainer = document.createElement('div');
            detailsContainer.className = 'aiops-details';

            const detailsToggle = document.createElement('div');
            detailsToggle.className = 'details-toggle';
            detailsToggle.innerHTML = `
                <svg class="toggle-icon" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M9 18L15 12L9 6" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
                <span>查看详细步骤 (${details.length}条)</span>
            `;

            const detailsContent = document.createElement('div');
            detailsContent.className = 'details-content';
            
            details.forEach((detail, index) => {
                const detailItem = document.createElement('div');
                detailItem.className = 'detail-item';
                detailItem.innerHTML = `<strong>步骤 ${index + 1}:</strong> ${this.escapeHtml(detail)}`;
                detailsContent.appendChild(detailItem);
            });

            // 点击切换折叠状态
            detailsToggle.addEventListener('click', () => {
                detailsContent.classList.toggle('expanded');
                detailsToggle.classList.toggle('expanded');
            });

            detailsContainer.appendChild(detailsToggle);
            detailsContainer.appendChild(detailsContent);
            messageContentWrapper.appendChild(detailsContainer);
        }

        // 主要响应内容 - 后显示（使用Markdown渲染）
        const messageContent = document.createElement('div');
        messageContent.className = 'message-content';
        messageContent.innerHTML = this.renderMarkdown(response);
        // 高亮代码块
        this.highlightCodeBlocks(messageContent);
        messageContentWrapper.appendChild(messageContent);
        messageDiv.appendChild(messageContentWrapper);
        
        if (this.chatMessages) {
            this.chatMessages.appendChild(messageDiv);
            this.scrollToBottom();
        }

        return messageDiv;
    }

    // HTML转义
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // 触发智能运维（点击智能运维按钮时直接调用）
    async triggerAIOps() {
        if (this.isStreaming) {
            this.showNotification('请等待当前操作完成', 'warning');
            return;
        }

        // 新建对话
        this.newChat();
        this.currentChatTitle = window.AIOpsStream.createSessionTitle(new Date());
        
        // 添加"分析中..."的消息（带旋转动画）
        const loadingMessage = this.addLoadingMessage('分析中...');
        this.currentAIOpsMessage = loadingMessage; // 保存消息引用用于后续更新
        
        // 设置发送状态
        this.isStreaming = true;
        this.updateUI();

        try {
            await this.sendAIOpsRequest(loadingMessage);
        } catch (error) {
            console.error('智能运维分析失败:', error);
            // 更新消息为错误信息
            if (loadingMessage) {
                const messageContent = loadingMessage.querySelector('.message-content');
                if (messageContent) {
                    messageContent.textContent = '抱歉，智能运维分析时出现错误：' + error.message;
                }
            }
        } finally {
            this.isStreaming = false;
            this.currentAIOpsMessage = null;
            this.updateUI();
        }
    }

    // 显示/隐藏加载遮罩层
    showLoadingOverlay(show) {
        if (this.loadingOverlay) {
            if (show) {
                this.loadingOverlay.style.display = 'flex';
                // 更新文字为智能运维
                const loadingText = this.loadingOverlay.querySelector('.loading-text');
                const loadingSubtext = this.loadingOverlay.querySelector('.loading-subtext');
                if (loadingText) loadingText.textContent = '智能运维分析中，请稍候...';
                if (loadingSubtext) loadingSubtext.textContent = '后端正在处理，请耐心等待';
                // 防止页面滚动
                document.body.style.overflow = 'hidden';
            } else {
                this.loadingOverlay.style.display = 'none';
                // 恢复页面滚动
                document.body.style.overflow = '';
            }
        }
    }

    // 显示/隐藏上传遮罩层
    showUploadOverlay(show, fileName = '', phase = 'uploading') {
        if (this.loadingOverlay) {
            if (show) {
                this.loadingOverlay.style.display = 'flex';
                const loadingText = this.loadingOverlay.querySelector('.loading-text');
                const loadingSubtext = this.loadingOverlay.querySelector('.loading-subtext');
                const isIndexing = phase === 'indexing';
                if (loadingText) {
                    loadingText.textContent = isIndexing ? '正在建立知识库索引...' : '正在上传文件...';
                }
                if (loadingSubtext) {
                    const action = isIndexing ? '索引' : '上传';
                    loadingSubtext.textContent = fileName ? `${action}: ${fileName}` : '请稍候';
                }
                // 防止页面滚动
                document.body.style.overflow = 'hidden';
            } else {
                this.loadingOverlay.style.display = 'none';
                // 恢复页面滚动
                document.body.style.overflow = '';
            }
        }
    }
}

// 添加CSS动画
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from {
            transform: translateX(100%);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }
    
    @keyframes slideOut {
        from {
            transform: translateX(0);
            opacity: 1;
        }
        to {
            transform: translateX(100%);
            opacity: 0;
        }
    }
`;
document.head.appendChild(style);

// 初始化应用
document.addEventListener('DOMContentLoaded', () => {
    new SuperBizAgentApp();
});
