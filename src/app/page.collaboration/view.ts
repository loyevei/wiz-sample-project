import { OnInit } from '@angular/core';
import { Service } from '@wiz/libs/portal/season/service';

declare const wiz: any;

export class Component implements OnInit {
    public activeTab: string = 'projects';
    public tabs = [
        { id: 'projects', label: '프로젝트' },
        { id: 'discussions', label: '토론' },
        { id: 'activity', label: '활동/알림' }
    ];

    // ===== Projects =====
    public projects: any[] = [];
    public projectSearch: string = '';
    public showProjectForm: boolean = false;
    public editingProject: any = null;
    public projectForm: any = {
        name: '',
        description: '',
        members: '',
        status: 'active'
    };

    // ===== Discussions =====
    public discussions: any[] = [];
    public discussionSearch: string = '';
    public showDiscussionForm: boolean = false;
    public editingDiscussion: any = null;
    public discussionForm: any = {
        title: '',
        content: ''
    };
    public selectedDiscussion: any = null;
    public replyContent: string = '';

    // ===== Activity =====
    public activities: any[] = [];

    constructor(public service: Service) { }

    public async ngOnInit() {
        await this.service.init();
        await this.loadProjects();
        await this.loadDiscussions();
        await this.loadActivity();
        await this.service.render();
    }

    public async switchTab(tabId: string) {
        this.activeTab = tabId;
        this.selectedDiscussion = null;
        await this.service.render();
    }

    // ===== Project Methods =====
    public async loadProjects() {
        try {
            const { code, data } = await wiz.call("list_projects");
            if (code === 200) this.projects = data || [];
        } catch (e) { }
    }

    public filteredProjects() {
        if (!this.projectSearch) return this.projects;
        const f = this.projectSearch.toLowerCase();
        return this.projects.filter((p: any) =>
            p.name.toLowerCase().includes(f) ||
            (p.description || '').toLowerCase().includes(f)
        );
    }

    public openProjectForm(project?: any) {
        if (project) {
            this.editingProject = project;
            this.projectForm = {
                name: project.name,
                description: project.description || '',
                members: (project.members || []).join(', '),
                status: project.status || 'active'
            };
        } else {
            this.editingProject = null;
            this.projectForm = {
                name: '',
                description: '',
                members: '',
                status: 'active'
            };
        }
        this.showProjectForm = true;
        this.service.render();
    }

    public cancelProjectForm() {
        this.showProjectForm = false;
        this.editingProject = null;
        this.service.render();
    }

    public async saveProject() {
        if (!this.projectForm.name.trim()) return;
        try {
            const payload: any = {
                name: this.projectForm.name,
                description: this.projectForm.description,
                members: this.projectForm.members.split(',').map((m: string) => m.trim()).filter((m: string) => m),
                status: this.projectForm.status
            };
            if (this.editingProject) payload.id = this.editingProject.id;
            const { code } = await wiz.call("save_project", payload);
            if (code === 200) {
                this.showProjectForm = false;
                this.editingProject = null;
                await this.loadProjects();
                await this.loadActivity();
            }
        } catch (e) { }
        await this.service.render();
    }

    public async deleteProject(projectId: string) {
        if (!confirm('이 프로젝트를 삭제하시겠습니까?')) return;
        try {
            const { code } = await wiz.call("delete_project", { id: projectId });
            if (code === 200) {
                await this.loadProjects();
                await this.loadActivity();
            }
        } catch (e) { }
        await this.service.render();
    }

    public getStatusClass(status: string): string {
        switch (status) {
            case 'active': return 'bg-green-100 text-green-700';
            case 'completed': return 'bg-blue-100 text-blue-700';
            case 'paused': return 'bg-yellow-100 text-yellow-700';
            case 'archived': return 'bg-gray-100 text-gray-600';
            default: return 'bg-gray-100 text-gray-600';
        }
    }

    public getStatusLabel(status: string): string {
        switch (status) {
            case 'active': return '진행 중';
            case 'completed': return '완료';
            case 'paused': return '일시중지';
            case 'archived': return '보관';
            default: return status;
        }
    }

    // ===== Discussion Methods =====
    public async loadDiscussions() {
        try {
            const { code, data } = await wiz.call("list_discussions");
            if (code === 200) this.discussions = data || [];
        } catch (e) { }
    }

    public filteredDiscussions() {
        if (!this.discussionSearch) return this.discussions;
        const f = this.discussionSearch.toLowerCase();
        return this.discussions.filter((d: any) =>
            d.title.toLowerCase().includes(f) ||
            (d.content || '').toLowerCase().includes(f) ||
            (d.author || '').toLowerCase().includes(f)
        );
    }

    public openDiscussionForm(discussion?: any) {
        if (discussion) {
            this.editingDiscussion = discussion;
            this.discussionForm = {
                title: discussion.title,
                content: discussion.content || ''
            };
        } else {
            this.editingDiscussion = null;
            this.discussionForm = {
                title: '',
                content: ''
            };
        }
        this.showDiscussionForm = true;
        this.service.render();
    }

    public cancelDiscussionForm() {
        this.showDiscussionForm = false;
        this.editingDiscussion = null;
        this.service.render();
    }

    public async saveDiscussion() {
        if (!this.discussionForm.title.trim()) return;
        try {
            const payload: any = {
                title: this.discussionForm.title,
                content: this.discussionForm.content
            };
            if (this.editingDiscussion) payload.id = this.editingDiscussion.id;
            const { code } = await wiz.call("save_discussion", payload);
            if (code === 200) {
                this.showDiscussionForm = false;
                this.editingDiscussion = null;
                await this.loadDiscussions();
                await this.loadActivity();
            }
        } catch (e) { }
        await this.service.render();
    }

    public async deleteDiscussion(discussionId: string) {
        if (!confirm('이 토론을 삭제하시겠습니까?')) return;
        try {
            const { code } = await wiz.call("delete_discussion", { id: discussionId });
            if (code === 200) {
                if (this.selectedDiscussion && this.selectedDiscussion.id === discussionId) {
                    this.selectedDiscussion = null;
                }
                await this.loadDiscussions();
                await this.loadActivity();
            }
        } catch (e) { }
        await this.service.render();
    }

    public async selectDiscussion(discussion: any) {
        this.selectedDiscussion = discussion;
        await this.service.render();
    }

    public backToList() {
        this.selectedDiscussion = null;
        this.replyContent = '';
        this.service.render();
    }

    public async submitReply() {
        if (!this.replyContent.trim() || !this.selectedDiscussion) return;
        try {
            const { code } = await wiz.call("save_discussion", {
                id: this.selectedDiscussion.id,
                reply: this.replyContent
            });
            if (code === 200) {
                this.replyContent = '';
                await this.loadDiscussions();
                const updated = this.discussions.find((d: any) => d.id === this.selectedDiscussion.id);
                if (updated) this.selectedDiscussion = updated;
                await this.loadActivity();
            }
        } catch (e) { }
        await this.service.render();
    }

    // ===== Activity Methods =====
    public async loadActivity() {
        try {
            const { code, data } = await wiz.call("list_activity");
            if (code === 200) this.activities = data || [];
        } catch (e) { }
    }

    public getActivityIcon(type: string): string {
        switch (type) {
            case 'project_created': return 'M12 10.5v6m3-3H9m4.06-7.19-2.12-2.12a1.5 1.5 0 0 0-1.061-.44H4.5A2.25 2.25 0 0 0 2.25 6v12a2.25 2.25 0 0 0 2.25 2.25h15A2.25 2.25 0 0 0 21.75 18V9a2.25 2.25 0 0 0-2.25-2.25h-5.379a1.5 1.5 0 0 1-1.06-.44Z';
            case 'project_updated': return 'M16.862 4.487l1.687-1.688a1.875 1.875 0 1 1 2.652 2.652L10.582 16.07a4.5 4.5 0 0 1-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 0 1 1.13-1.897l8.932-8.931Zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0 1 15.75 21H5.25A2.25 2.25 0 0 1 3 18.75V8.25A2.25 2.25 0 0 1 5.25 6H10';
            case 'project_deleted': return 'M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 0 1-2.244 2.077H8.084a2.25 2.25 0 0 1-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 0 0-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 0 1 3.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 0 0-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 0 0-7.5 0';
            case 'discussion_created': return 'M7.5 8.25h9m-9 3H12m-9.75 1.51c0 1.6 1.123 2.994 2.707 3.227 1.129.166 2.27.293 3.423.379.35.026.67.21.865.501L12 21l2.755-4.133a1.14 1.14 0 0 1 .865-.501 48.172 48.172 0 0 0 3.423-.379c1.584-.233 2.707-1.626 2.707-3.228V6.741c0-1.602-1.123-2.995-2.707-3.228A48.394 48.394 0 0 0 12 3c-2.392 0-4.744.175-7.043.513C3.373 3.746 2.25 5.14 2.25 6.741v6.018Z';
            case 'reply_added': return 'M8.625 12a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm0 0H8.25m4.125 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm0 0H12m4.125 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm0 0h-.375M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 0 1-2.555-.337A5.972 5.972 0 0 1 5.41 20.97a5.969 5.969 0 0 1-.474-.065 4.48 4.48 0 0 0 .978-2.025c.09-.457-.133-.901-.467-1.226C3.93 16.178 3 14.189 3 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25Z';
            default: return 'M11.25 11.25l.041-.02a.75.75 0 0 1 1.063.852l-.708 2.836a.75.75 0 0 0 1.063.853l.041-.021M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Zm-9-3.75h.008v.008H12V8.25Z';
        }
    }

    public getActivityColor(type: string): string {
        switch (type) {
            case 'project_created': return 'bg-teal-100 text-teal-600';
            case 'project_updated': return 'bg-blue-100 text-blue-600';
            case 'project_deleted': return 'bg-red-100 text-red-600';
            case 'discussion_created': return 'bg-purple-100 text-purple-600';
            case 'reply_added': return 'bg-amber-100 text-amber-600';
            default: return 'bg-gray-100 text-gray-600';
        }
    }

    public formatDate(dateStr: string): string {
        if (!dateStr) return '';
        const d = new Date(dateStr);
        return d.toLocaleDateString('ko-KR', { year: 'numeric', month: '2-digit', day: '2-digit' });
    }

    public formatDateTime(dateStr: string): string {
        if (!dateStr) return '';
        const d = new Date(dateStr);
        return d.toLocaleDateString('ko-KR', {
            year: 'numeric', month: '2-digit', day: '2-digit',
            hour: '2-digit', minute: '2-digit'
        });
    }

    public timeAgo(dateStr: string): string {
        if (!dateStr) return '';
        const now = new Date();
        const d = new Date(dateStr);
        const diff = Math.floor((now.getTime() - d.getTime()) / 1000);
        if (diff < 60) return '방금 전';
        if (diff < 3600) return `${Math.floor(diff / 60)}분 전`;
        if (diff < 86400) return `${Math.floor(diff / 3600)}시간 전`;
        if (diff < 604800) return `${Math.floor(diff / 86400)}일 전`;
        return this.formatDate(dateStr);
    }
}
