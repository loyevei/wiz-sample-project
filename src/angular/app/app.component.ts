import { Component, OnInit, ChangeDetectorRef, enableProdMode } from '@angular/core';
import { Router } from '@angular/router';
import { Service } from '@wiz/libs/portal/season/service';
import { TranslateService } from '@ngx-translate/core';

@Component({
    selector: 'app-root',
    templateUrl: './app.component.html',
    styleUrls: ['./app.component.scss']
})
export class AppComponent implements OnInit {
    constructor(
        public service: Service,
        public router: Router,
        public ref: ChangeDetectorRef,
        public translate: TranslateService
    ) {
        window['MonacoEnvironment'] = {
            getWorkerUrl: function (moduleId: string, label: string) {
                return `/lib/vs/base/worker/workerMain.js`;
            }
        };
    }

    public async ngOnInit() {
        enableProdMode();
        await this.service.init(this);
    }
}