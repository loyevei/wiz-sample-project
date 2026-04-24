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

    public chatMessages: any[] = [];
    public chatHistory: any[] = [];
    public chatInput: string = '';
    public chatLoading: boolean = false;
    public chatAbortController: AbortController | null = null;

    public async ngOnInit() {
        await this.service.init();
        await this.service.render();
    }

    public ngOnDestroy() { }

    public async sendChat() {
        const message = this.chatInput.trim();
        if (!message || this.chatLoading) return;

        this.chatMessages.push({ role: 'user', content: message });
        this.chatInput = '';
        this.chatLoading = true;
        this.chatAbortController = new AbortController();

        const assistantMsg: any = {
            role: 'assistant',
            content: '',
            previewContent: '현재까지 핵심 포인트를 정리하고 있습니다.',
            navigationCard: {
                loading: true,
                summary: '최종 결과와 연결할 페이지를 준비하고 있습니다.',
                actionLabel: '바로 이동',
            },
            pageResultCard: {
                loading: true,
                page: '분석 경로 선정 중',
                tab: '검색 준비',
                summary: '질문에 맞는 페이지 결과를 먼저 읽고 있습니다.',
                query: message,
                paramsText: '',
                evidenceLines: []
            },
            answerQuality: this.buildAnswerQuality()
        };
        this.chatMessages.push(assistantMsg);
        const assistantIdx = this.chatMessages.length - 1;
        let receivedDone = false;
        let receivedHistory = false;

        const markStreamComplete = () => {
            if (!this.chatLoading) return;
            this.chatLoading = false;
            this.cdr.detectChanges();
        };
        await this.service.render();

        const params = new URLSearchParams();
        params.append('message', message);
        params.append('history', JSON.stringify(this.chatHistory));

        try {
            const response = await fetch(
                `/wiz/api/page.agent.v2/agent_chat`,
                { method: 'POST', body: params, signal: this.chatAbortController.signal }
            );

            if (!response.ok) {
                let errorMessage = `요청 실패 (${response.status})`;
                try {
                    const payload = await response.json();
                    errorMessage = payload?.data?.message || payload?.message || errorMessage;
                } catch (e) { }
                throw new Error(errorMessage);
            }

            if (!response.body) {
                throw new Error('응답 스트림을 열지 못했습니다.');
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';
            const completionTimeoutToken = {};

            const flushBuffer = (force: boolean = false) => {
                const chunks = force ? [buffer] : buffer.split('\n\n');
                if (!force) {
                    buffer = chunks.pop() || '';
                } else {
                    buffer = '';
                }

                for (const chunk of chunks) {
                    const line = chunk.trim();
                    if (!line.startsWith('data: ')) continue;
                    try {
                        const result = this.handleChatEvent(this.chatMessages[assistantIdx], JSON.parse(line.slice(6)));
                        receivedDone = receivedDone || result.done;
                        receivedHistory = receivedHistory || result.history;
                        if (result.done) {
                            markStreamComplete();
                        }
                    } catch (e) { }
                }
            };

            const readNextChunk = async () => {
                const pendingRead = reader.read().catch(() => ({ done: true, value: undefined }));
                if (!receivedDone) {
                    return pendingRead;
                }

                let timeoutHandle: any = null;
                const timeoutPromise = new Promise<any>((resolve) => {
                    timeoutHandle = setTimeout(() => resolve(completionTimeoutToken), 400);
                });
                const result = await Promise.race([pendingRead, timeoutPromise]);
                if (timeoutHandle) {
                    clearTimeout(timeoutHandle);
                }

                if (result === completionTimeoutToken) {
                    await reader.cancel().catch(() => { });
                    return { done: true, value: undefined };
                }

                return result;
            };

            while (true) {
                const { done, value } = await readNextChunk();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                flushBuffer();
                this.cdr.detectChanges();
            }

            buffer += decoder.decode();
            if (buffer.trim()) {
                flushBuffer(true);
            }
        } catch (e: any) {
            if (e.name !== 'AbortError') {
                this.handleChatEvent(this.chatMessages[assistantIdx], {
                    type: 'error',
                    message: e?.message || '연결이 끊어졌습니다.'
                });
            }
        }

        if (!receivedDone) {
            this.finalizeAssistantState(this.chatMessages[assistantIdx]);
        }

        if (!receivedHistory) {
            const assistantContent = String(this.chatMessages[assistantIdx]?.content || this.chatMessages[assistantIdx]?.previewContent || '').trim();
            this.chatHistory = [
                ...this.chatHistory,
                { role: 'user', content: message },
                { role: 'assistant', content: assistantContent }
            ];
        }

        this.chatAbortController = null;
        this.chatLoading = false;
        this.finalizeAssistantState(this.chatMessages[assistantIdx]);
        await this.service.render();
        this.cdr.detectChanges();
    }

    private handleChatEvent(msg: any, event: any): { done: boolean, history: boolean } {
        if (!msg || !event || typeof event !== 'object') {
            return { done: false, history: false };
        }

        if (event.type === 'text_delta') {
            msg.content = (msg.content || '') + (event.content || '');
            msg._streamedDeltas = true;
            return { done: false, history: false };
        }

        if (event.type === 'text_clear') {
            msg.content = '';
            msg._streamedDeltas = false;
            return { done: false, history: false };
        }

        if (event.type === 'text') {
            const incoming = String(event.content || '').trim();
            if (event.stage === 'preview') {
                msg.previewContent = incoming || msg.previewContent;
            } else if (incoming) {
                if (msg._streamedDeltas) {
                    msg.content = incoming;
                    msg._streamedDeltas = false;
                } else {
                    const previous = String(msg.content || '').trim();
                    msg.content = previous && previous !== incoming ? `${previous}\n\n${incoming}` : incoming;
                }
            }
            return { done: false, history: false };
        }

        if (event.type === 'quality') {
            this.applyQualityEvent(msg, event);
            return { done: false, history: false };
        }

        if (event.type === 'tool_result') {
            this.applyToolResult(msg, event);
            return { done: false, history: false };
        }

        if (event.type === 'orchestration') {
            this.applyOrchestrationEvent(msg, event);
            return { done: false, history: false };
        }

        if (event.type === 'pipeline' && event.detail) {
            msg.previewContent = event.detail;
            return { done: false, history: false };
        }

        if (event.type === 'history') {
            this.chatHistory = Array.isArray(event.messages) ? event.messages : this.chatHistory;
            return { done: false, history: true };
        }

        if (event.type === 'error') {
            const errorMessage = String(event.message || '에이전트 처리 중 오류가 발생했습니다.').trim();
            const previous = String(msg.content || '').trim();
            msg.content = previous ? `${previous}\n\n**Error:** ${errorMessage}` : `**Error:** ${errorMessage}`;
            msg.previewContent = errorMessage;
            return { done: false, history: false };
        }

        if (event.type === 'done') {
            this.finalizeAssistantState(msg);
            return { done: true, history: false };
        }

        return { done: false, history: false };
    }

    public cancelChat() {
        this.chatAbortController?.abort();
        this.chatLoading = false;
    }

    public onKeydown(event: KeyboardEvent) {
        if (event.key === 'Enter' && !event.shiftKey) {
            event.preventDefault();
            this.sendChat();
        }
    }

    public renderMarkdown(text: string): SafeHtml {
        if (!text) return this.sanitizer.bypassSecurityTrustHtml('');
        // minimal: render as pre-wrap text
        const escaped = text
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;');
        return this.sanitizer.bypassSecurityTrustHtml(`<pre style="white-space: pre-wrap; margin:0;">${escaped}</pre>`);
    }

    private buildAnswerQuality(): any {
        return {
            stage: 'pending',
            detail: '',
            answerStyle: '',
            confidence: '',
            evidenceCount: 0,
            avgScore: null,
            synthesisPoints: [],
            verificationChecks: [],
            sources: [],
            llmUsed: false,
        };
    }

    private applyQualityEvent(msg: any, event: any) {
        const quality = msg.answerQuality || this.buildAnswerQuality();
        quality.stage = event.stage || quality.stage;
        quality.detail = event.detail || quality.detail;
        if (event.answerStyle) quality.answerStyle = event.answerStyle;
        if (event.confidence) quality.confidence = event.confidence;
        if (typeof event.llmUsed === 'boolean') quality.llmUsed = event.llmUsed;
        if (Number.isFinite(event.evidenceCount)) quality.evidenceCount = event.evidenceCount;
        if (event.avgScore !== null && event.avgScore !== undefined && Number.isFinite(Number(event.avgScore))) {
            quality.avgScore = Number(event.avgScore);
        }
        if (Array.isArray(event.synthesisPoints)) quality.synthesisPoints = event.synthesisPoints;
        if (Array.isArray(event.verificationChecks)) quality.verificationChecks = event.verificationChecks;
        if (Array.isArray(event.sources)) quality.sources = event.sources;
        msg.answerQuality = quality;
        msg.previewContent = quality.detail || quality.synthesisPoints?.[0] || msg.previewContent;
    }

    private applyToolResult(msg: any, event: any) {
        const name = String(event.name || '').toLowerCase();
        let result = event.result || {};
        if (typeof result === 'string') {
            try {
                result = JSON.parse(result);
            } catch (e) {
                result = { summary: result };
            }
        }

        if (name === 'read_page_results') {
            msg.pageResultCard = {
                loading: false,
                page: result.page || msg.pageResultCard?.page || '-',
                tab: result.tab || msg.pageResultCard?.tab || '-',
                summary: result.summary || '페이지 결과를 바탕으로 핵심 포인트를 정리했습니다.',
                query: result.query || msg.pageResultCard?.query || '',
                paramsText: this.stringifyParams(result.params || {}),
                evidenceLines: Array.isArray(result.evidence_lines) ? result.evidence_lines : []
            };
            msg.previewContent = msg.pageResultCard.summary;
            return;
        }

        if (name === 'navigate_to_page') {
            msg.navigationCard = {
                loading: false,
                summary: result.summary || `${result.page || '-'}${result.tab ? ` / ${result.tab}` : ''} 페이지로 이어서 볼 수 있습니다.`,
                actionLabel: '바로 이동',
                payload: result
            };
        }
    }

    private applyOrchestrationEvent(msg: any, event: any) {
        msg.previewContent = `관련 페이지 ${event.page || '-'}${event.tab ? `의 ${event.tab}` : ''} 결과를 바탕으로 답변 방향을 정하고 있습니다.`;
        if (msg.pageResultCard) {
            msg.pageResultCard.page = event.page || msg.pageResultCard.page;
            msg.pageResultCard.tab = event.tab || msg.pageResultCard.tab;
            msg.pageResultCard.summary = `선택된 경로 ${event.page || '-'}${event.tab ? ` · ${event.tab}` : ''} 기준으로 결과를 준비하고 있습니다.`;
        }
    }

    private finalizeAssistantState(msg: any) {
        if (msg.navigationCard?.loading) {
            msg.navigationCard.loading = false;
            msg.navigationCard.summary = '이번 답변은 별도의 페이지 이동 없이 여기서 바로 마무리했습니다.';
            msg.navigationCard.actionLabel = '이동 없음';
        }
        if (msg.pageResultCard?.loading) {
            msg.pageResultCard.loading = false;
            msg.pageResultCard.summary = msg.pageResultCard.summary || '페이지 결과 없이 현재 대화 문맥으로 답변을 정리했습니다.';
        }
        if (!String(msg.content || '').trim()) {
            const fallback = [
                msg.pageResultCard?.summary,
                msg.navigationCard?.summary,
                msg.answerQuality?.detail,
                msg.previewContent,
            ].map((item) => String(item || '').trim()).find(Boolean);
            if (fallback) {
                msg.content = fallback;
            }
        }
        if (!String(msg.previewContent || '').trim() && String(msg.content || '').trim()) {
            msg.previewContent = String(msg.content || '').split(/\n+/)[0];
        }
    }

    private stringifyParams(params: any): string {
        if (!params || typeof params !== 'object') return '';
        const entries = Object.entries(params).filter(([_, value]) => value !== undefined && value !== null && `${value}`.trim() !== '');
        return entries.map(([key, value]) => `${key}=${value}`).join(', ');
    }

    public shouldShowQualityCard(msg: any): boolean {
        return this.hasQualityInsights(msg) || Boolean(msg?.content || msg?.previewContent || msg?.typingActive);
    }

    public getAssistantPreviewLines(msg: any): string[] {
        const preview = String(msg?.previewContent || '').trim();
        if (!preview) return ['질문 의도와 근거 후보를 정리하고 있습니다.'];
        return preview.split(/\n+/).map((line) => line.trim()).filter(Boolean).slice(0, 3);
    }

    public hasQualityInsights(msg: any): boolean {
        const quality = msg.answerQuality || {};
        return Boolean(
            quality.detail
            || quality.llmUsed
            || (quality.synthesisPoints || []).length > 0
            || (quality.verificationChecks || []).length > 0
            || (quality.evidenceCount || 0) > 0
        );
    }

    public getQualityBadges(msg: any): string[] {
        const quality = msg.answerQuality || {};
        const badges: string[] = [];
        if (quality.llmUsed) badges.push('LLM 해석');
        if (quality.answerStyle) badges.push(quality.answerStyle);
        if (quality.confidence) badges.push(`신뢰도 ${quality.confidence}`);
        if ((quality.evidenceCount || 0) > 0) badges.push(`근거 ${quality.evidenceCount}건`);
        if (quality.avgScore !== null && quality.avgScore !== undefined && Number.isFinite(Number(quality.avgScore))) {
            badges.push(`평균 ${Number(quality.avgScore).toFixed(4)}`);
        }
        return badges;
    }
}
