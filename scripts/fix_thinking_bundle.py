from pathlib import Path

path = Path('/opt/app/project/main/bundle/www/main.js')
text = path.read_text()
replacements = [
    (
        'class="flex items-center gap-2 w-full py-1 text-left group" (click)="toggleTrace(msg)"',
        'class="flex items-center gap-2 w-full py-1 text-left group" (click)="msg.traceCompleted &amp;&amp; toggleTrace(msg)"',
    ),
    (
        '[class.rotate-90]="msg.traceOpen"',
        '[class.rotate-90]="!msg.traceCompleted || msg.traceOpen"',
    ),
    (
        '*ngIf="msg.traceOpen"',
        '*ngIf="!msg.traceCompleted || msg.traceOpen"',
    ),
    (
        'createAssistantMessage(){return{role:"assistant",content:"",collapsed:!1,traceSteps:[],traceOpen:!1,traceCompleted:!1,executionPlan:null,toolCalls:[],navigationCard:null,pageResultCard:null,answerQuality:null,evidenceItems:[],evidenceOpen:!1,error:!1,typingActive:!1,fullContent:"",currentDescription:""}}',
        'createAssistantMessage(){return{role:"assistant",content:"",collapsed:!1,traceSteps:this.buildPendingTraceSteps(),traceOpen:!0,traceCompleted:!1,executionPlan:null,toolCalls:[],navigationCard:null,pageResultCard:null,answerQuality:null,evidenceItems:[],evidenceOpen:!1,error:!1,typingActive:!1,fullContent:"",currentDescription:""}}',
    ),
    (
        'case"orchestration":e.traceSteps=(t.trace_steps||[]).map(r=>({id:r.id,title:r.title||"",status:r.status||"pending",detail:r.detail||""})),e.traceOpen=!1,',
        'case"orchestration":e.traceSteps=(t.trace_steps||[]).map(r=>({id:r.id,title:r.title||"",status:r.status||"pending",detail:r.detail||""})),e.traceOpen=!0,',
    ),
    (
        'e.traceCompleted=!0}this.typewriterTimers.has(e)&&(clearInterval(this.typewriterTimers.get(e)),this.typewriterTimers.delete(e),e.fullContent&&(e.content=e.fullContent),e.typingActive=!1),this.chatLoading=!1',
        'e.traceCompleted=!0,e.traceOpen=!1}this.typewriterTimers.has(e)&&(clearInterval(this.typewriterTimers.get(e)),this.typewriterTimers.delete(e),e.fullContent&&(e.content=e.fullContent),e.typingActive=!1),this.chatLoading=!1',
    ),
    (
        '}this.scrollToBottom(),this.service.render()}',
        '}e.traceSteps?.length>0&&!e.traceCompleted&&t.type!=="done"&&(e.traceOpen=!0),this.scrollToBottom(),this.service.render()}',
    ),
    (
        'class="flex w-full items-center justify-between gap-3 border-b border-slate-100 bg-slate-50/80 px-5 py-4 text-left" (click)="toggleTrace(msg)"',
        'class="flex w-full items-center justify-between gap-3 border-b border-slate-100 bg-slate-50/80 px-5 py-4 text-left" (click)="msg.traceCompleted &amp;&amp; toggleTrace(msg)"',
    ),
    (
        "{{msg.traceCompleted ? '요약 보기' : (msg.traceOpen ? '접기' : '펼치기')}}",
        "{{msg.traceCompleted ? (msg.traceOpen ? '접기' : '펼치기') : '진행 중'}}",
    ),
]

for old, new in replacements:
    print(text.count(old))
    text = text.replace(old, new)

path.write_text(text)
print('done')
