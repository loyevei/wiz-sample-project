import { OnInit, OnDestroy, ViewChild, ElementRef, ChangeDetectorRef } from '@angular/core';
import { DomSanitizer, SafeHtml } from '@angular/platform-browser';
import { Service } from '@wiz/libs/portal/season/service';

declare const wiz: any;

export class Component implements OnInit, OnDestroy {
    @ViewChild('chatContainer') chatContainer!: ElementRef;
    @ViewChild('chatInputEl') chatInputEl!: ElementRef;

    constructor(
        public service: Service,
        private sanitizer: DomSanitizer,
        private cdr: ChangeDetectorRef
    ) { }

    // =========================================================================
    // State
    // =========================================================================
    public chatMessages: any[] = [];
    public chatHistory: any[] = [];
    public chatInput: string = '';
    public chatLoading: boolean = false;
    public chatAbortController: AbortController | null = null;

    // Tool 목록
    public availableTools: any[] = [];

    // 페이지 아이콘/색상 매핑
    public pageConfig: any = {
        research: { icon: '🔬', label_ko: '주제 발굴', label_en: 'Research Discovery', color: 'violet' },
        prediction: { icon: '📊', label_ko: '공정 예측', label_en: 'Process Prediction', color: 'blue' },
        diagnosis: { icon: '🩺', label_ko: '진단 분석', label_en: 'Diagnostics Analysis', color: 'emerald' },
        theory: { icon: '📐', label_ko: '이론 연구', label_en: 'Theory Analysis', color: 'amber' }
    };

    // =========================================================================
    // Lifecycle
    // =========================================================================
    public async ngOnInit() {
        await this.service.init();
        await this.loadTools();
        await this.service.render();
    }

    public ngOnDestroy() { }

    // =========================================================================
    // Load Tools
    // =========================================================================
    public async loadTools() {
        const res = await wiz.call("agent_tools");
        if (res.code === 200) {
            this.availableTools = res.data;
        }
    }

    // =========================================================================
    // Send Chat (SSE Streaming)
    // =========================================================================
    public async sendChat() {
        const message = this.chatInput.trim();
        if (!message || this.chatLoading) return;

        // Add user message
        this.chatMessages.push({ role: 'user', content: message, collapsed: false });
        this.chatInput = '';
        this.chatLoading = true;
        this.chatAbortController = new AbortController();

        // Add empty assistant message
        const assistantMsg: any = {
            role: 'assistant',
            content: '',
            toolCalls: [],
            navigations: [],
            intent: '',
            collapsed: false
        };
        this.chatMessages.push(assistantMsg);
        const assistantIdx = this.chatMessages.length - 1;
        await this.service.render();
        this.scrollToBottom();

        // SSE Fetch
        const params = new URLSearchParams();
        params.append('message', message);
        params.append('history', JSON.stringify(this.chatHistory));

        try {
            const response = await fetch(
                `/wiz/api/page.agent/agent_chat`,
                {
                    method: 'POST',
                    body: params,
                    signal: this.chatAbortController.signal
                }
            );

            const reader = response.body!.getReader();
            const decoder = new TextDecoder();
            let buffer = '';

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n\n');
                buffer = lines.pop() || '';

                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        try {
                            const event = JSON.parse(line.slice(6));
                            this.handleChatEvent(event, assistantIdx);
                        } catch (e) { }
                    }
                }
            }
        } catch (e: any) {
            if (e.name !== 'AbortError') {
                this.chatMessages[assistantIdx].content += '\n\n**Error:** 연결이 끊어졌습니다.';
            }
        }

        this.chatLoading = false;
        await this.service.render();
        this.scrollToBottom();
    }

    // =========================================================================
    // Handle SSE Events
    // =========================================================================
    private handleChatEvent(event: any, assistantIdx: number) {
        const msg = this.chatMessages[assistantIdx];
        if (!msg) return;

        switch (event.type) {
            case 'text':
                msg.content += event.content;
                break;
            case 'tool_use':
                msg.toolCalls.push({
                    type: 'use',
                    id: event.id,
                    name: event.name,
                    input: event.input,
                    collapsed: true
                });
                break;
            case 'tool_result':
                // navigate_to_page 도구 결과 → 네비게이션 카드 추가
                if (event.name === 'navigate_to_page') {
                    try {
                        const navData = typeof event.result === 'string'
                            ? JSON.parse(event.result)
                            : event.result;
                        if (navData.action === 'navigate' && navData.url) {
                            msg.intent = navData.page;
                            msg.navigations.push({
                                page: navData.page,
                                url: navData.url,
                                tab: navData.tab,
                                query: navData.query,
                                title_ko: navData.title_ko,
                                title_en: navData.title_en,
                                params: navData.params || {}
                            });
                        }
                    } catch (e) { }
                }
                msg.toolCalls.push({
                    type: 'result',
                    id: event.id,
                    name: event.name,
                    result: event.result,
                    collapsed: true
                });
                break;
            case 'history':
                this.chatHistory = event.messages;
                break;
            case 'done':
                this.autoCollapsePreviousTurns();
                // 의도 분류 결과에 따른 자동 페이지 이동
                if (msg.navigations && msg.navigations.length > 0) {
                    const nav = msg.navigations[0];
                    setTimeout(() => {
                        this.navigateToPage(nav);
                    }, 2500);
                }
                break;
            case 'error':
                msg.content += `\n\n**Error:** ${event.message}`;
                break;
        }
        this.cdr.detectChanges();
        this.scrollToBottom();
    }

    // =========================================================================
    // Navigate to Page
    // =========================================================================
    public navigateToPage(nav: any) {
        if (nav && nav.url) {
            this.service.href(nav.url);
        }
    }

    public getPageConfig(page: string) {
        return this.pageConfig[page] || { icon: '📄', label_ko: page, label_en: page, color: 'gray' };
    }

    public getIntentBadgeClass(page: string): string {
        const classes: any = {
            research: 'bg-violet-100 text-violet-700 border-violet-200',
            prediction: 'bg-blue-100 text-blue-700 border-blue-200',
            diagnosis: 'bg-emerald-100 text-emerald-700 border-emerald-200',
            theory: 'bg-amber-100 text-amber-700 border-amber-200'
        };
        return classes[page] || 'bg-gray-100 text-gray-700 border-gray-200';
    }

    // =========================================================================
    // Cancel
    // =========================================================================
    public cancelChat() {
        if (this.chatAbortController) {
            this.chatAbortController.abort();
            this.chatAbortController = null;
        }
        this.chatLoading = false;
    }

    // =========================================================================
    // Turn Management
    // =========================================================================
    private autoCollapsePreviousTurns() {
        for (let i = 0; i < this.chatMessages.length - 2; i++) {
            this.chatMessages[i].collapsed = true;
        }
    }

    public toggleCollapse(idx: number) {
        if (this.chatMessages[idx]) {
            this.chatMessages[idx].collapsed = !this.chatMessages[idx].collapsed;
        }
    }

    public toggleToolCollapse(msg: any, tcIdx: number) {
        if (msg.toolCalls && msg.toolCalls[tcIdx]) {
            msg.toolCalls[tcIdx].collapsed = !msg.toolCalls[tcIdx].collapsed;
        }
    }

    // =========================================================================
    // Clear Chat
    // =========================================================================
    public clearChat() {
        this.chatMessages = [];
        this.chatHistory = [];
    }

    // =========================================================================
    // Markdown Rendering (simple)
    // =========================================================================
    public renderMarkdown(text: string): SafeHtml {
        if (!text) return this.sanitizer.bypassSecurityTrustHtml('');
        let html = text;
        // Code blocks
        html = html.replace(/```(\w*)\n([\s\S]*?)```/g, '<pre class="bg-gray-900 text-green-400 p-3 rounded-lg text-xs overflow-x-auto my-2"><code>$2</code></pre>');
        // Inline code
        html = html.replace(/`([^`]+)`/g, '<code class="bg-gray-100 text-pink-600 px-1 py-0.5 rounded text-xs">$1</code>');
        // Bold
        html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
        // Italic
        html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');
        // Headers
        html = html.replace(/^### (.+)$/gm, '<h4 class="font-semibold text-[14px] mt-3 mb-1">$1</h4>');
        html = html.replace(/^## (.+)$/gm, '<h3 class="font-semibold text-[15px] mt-3 mb-1">$1</h3>');
        html = html.replace(/^# (.+)$/gm, '<h2 class="font-bold text-base mt-3 mb-1">$1</h2>');
        // Unordered lists
        html = html.replace(/^- (.+)$/gm, '<li class="ml-4 list-disc">$1</li>');
        html = html.replace(/(<li.*<\/li>\n?)+/g, '<ul class="my-1">$&</ul>');
        // Line breaks
        html = html.replace(/\n/g, '<br>');
        return this.sanitizer.bypassSecurityTrustHtml(html);
    }

    // =========================================================================
    // Scroll
    // =========================================================================
    private scrollToBottom() {
        setTimeout(() => {
            if (this.chatContainer?.nativeElement) {
                this.chatContainer.nativeElement.scrollTop = this.chatContainer.nativeElement.scrollHeight;
            }
        }, 50);
    }

    // =========================================================================
    // Keyboard
    // =========================================================================
    public onKeydown(event: KeyboardEvent) {
        if (event.key === 'Enter' && !event.shiftKey) {
            event.preventDefault();
            this.sendChat();
        }
    }

    // =========================================================================
    // Helpers
    // =========================================================================
    public formatToolInput(input: any): string {
        if (!input) return '';
        try {
            return JSON.stringify(input, null, 2);
        } catch {
            return String(input);
        }
    }

    public truncateResult(result: string, maxLen: number = 300): string {
        if (!result) return '';
        if (result.length <= maxLen) return result;
        return result.substring(0, maxLen) + '...';
    }
}
