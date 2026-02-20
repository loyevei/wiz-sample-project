import { OnInit, Input } from '@angular/core';

export class Component implements OnInit {
    @Input() className: any = "w-5 h-5 text-orange";

    public async ngOnInit() {
    }
}