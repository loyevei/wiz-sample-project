import { OnInit } from '@angular/core';
import { HostListener } from '@angular/core';
import { ViewChild } from '@angular/core';
import { ElementRef } from '@angular/core';
import { ChangeDetectorRef } from '@angular/core';
import { Service } from '@wiz/libs/portal/season/service';

export class Component implements OnInit {
    @ViewChild('chatSidebarPanel') chatSidebarPanel!: ElementRef;

    public chatSidebarWidth: number = 560;
    public isResizing: boolean = false;
    private readonly minChatSidebarWidth: number = 280;
    private readonly defaultChatSidebarWidth: number = 560;

    constructor(
        public service: Service,
        private cdr: ChangeDetectorRef,
    ) { }

    public async ngOnInit() {
        await this.service.init();
        const chatOpen = localStorage.getItem('chat_sidebar_open') === 'true';
        const savedWidth = Number(localStorage.getItem('chat_sidebar_width') || this.defaultChatSidebarWidth);
        this.chatSidebarWidth = this.clampChatSidebarWidth(savedWidth);
        if (chatOpen) {
            this.service.status.toggle('chat', true);
        }
    }

    @HostListener('document:click')
    public clickout() {
        this.service.status.toggle('navbar', false);
    }

    public isActive(link: string) {
        return location.pathname.indexOf(link) === 0
    }

    public toggleChat() {
        this.service.status.toggle('chat');
        localStorage.setItem('chat_sidebar_open', this.service.status.chat ? 'true' : 'false');
    }

    public startResize(event: MouseEvent) {
        event.preventDefault();
        event.stopPropagation();
        this.isResizing = true;
        document.body.classList.add('chat-resizing');
        document.body.style.cursor = 'col-resize';
        document.body.style.userSelect = 'none';
    }

    @HostListener('window:mousemove', ['$event'])
    public onResize(event: MouseEvent) {
        if (!this.isResizing) return;
        const nextWidth = window.innerWidth - event.clientX;
        this.chatSidebarWidth = this.clampChatSidebarWidth(nextWidth);
        this.applyChatSidebarWidth();
        this.cdr.detectChanges();
    }

    @HostListener('window:mouseup')
    public stopResize() {
        if (!this.isResizing) return;
        this.isResizing = false;
        document.body.classList.remove('chat-resizing');
        document.body.style.cursor = '';
        document.body.style.userSelect = '';
        localStorage.setItem('chat_sidebar_width', String(this.chatSidebarWidth));
    }

    @HostListener('window:resize')
    public onWindowResize() {
        this.chatSidebarWidth = this.clampChatSidebarWidth(this.chatSidebarWidth);
        this.applyChatSidebarWidth();
    }

    private clampChatSidebarWidth(width: number): number {
        const safeWidth = Number.isFinite(width) ? width : this.defaultChatSidebarWidth;
        const maxWidth = Math.min(1100, Math.max(420, Math.floor(window.innerWidth * 0.85)));
        return Math.min(Math.max(Math.round(safeWidth), this.minChatSidebarWidth), maxWidth);
    }

    private applyChatSidebarWidth() {
        if (!this.chatSidebarPanel?.nativeElement) return;
        const width = `${this.chatSidebarWidth}px`;
        this.chatSidebarPanel.nativeElement.style.width = width;
        this.chatSidebarPanel.nativeElement.style.flexBasis = width;
    }
}