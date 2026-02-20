import { OnInit, Input } from '@angular/core';
import { Service } from '@wiz/libs/portal/season/service';

export class Component implements OnInit {
    @Input() model: any = null;

    constructor(public service: Service) {
        if (!this.model) this.model = service.modal;
    }

    public async ngOnInit() {
    }

    public btnColorClass() {
        if (this.model.opts.status == 'warning')
            return 'inline-flex w-full justify-center rounded-md bg-yellow-600 px-3 py-2 text-sm font-semibold text-white shadow-sm hover:bg-yellow-500 sm:ml-3 sm:w-auto';
        if (this.model.opts.status == 'success')
            return 'inline-flex w-full justify-center rounded-md bg-indigo-600 px-3 py-2 text-sm font-semibold text-white shadow-sm hover:bg-indigo-500 sm:ml-3 sm:w-auto';
        return 'inline-flex w-full justify-center rounded-md bg-red-600 px-3 py-2 text-sm font-semibold text-white shadow-sm hover:bg-red-500 sm:ml-3 sm:w-auto';
    }
}