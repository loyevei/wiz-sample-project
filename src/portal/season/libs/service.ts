import { Injectable } from '@angular/core';
import { ChangeDetectorRef } from '@angular/core';

import Auth from './src/auth';
import Event from './src/event';
import Lang from './src/lang';
import Modal from './src/modal';
import Status from './src/status';

import Crypto from './util/crypto';
import File from './util/file';
import Request from './util/request';
import Formatter from './util/formatter';

@Injectable({ providedIn: 'root' })
export class Service {
    public app: ChangeDetectorRef;
    public inited: boolean = false;

    public auth: Auth;
    public modal: Modal;
    public event: Event;
    public lang: Lang;
    public status: Status;

    public crypto: Crypto;
    public file: File;
    public request: Request;
    public formatter: Formatter;

    constructor() { }

    public async init(app: any) {
        if (app) {
            this.app = app;

            this.crypto = new Crypto();
            this.file = new File();
            this.request = new Request();
            this.formatter = new Formatter();

            this.auth = new Auth(this);
            this.modal = new Modal(this);
            this.status = new Status(this);
            this.event = new Event(this);

            if (this.app.translate) {
                this.lang = new Lang(this);
                let lang: string = (navigator.language || navigator.userLanguage).substring(0, 2).toLowerCase();
                if (!['ko', 'en'].includes(lang)) lang = 'en';
                this.lang.set(lang);
            }

            await this.auth.init();
            this.inited = true;
            await this.render();
        }

        await this.auth.update();
        return this;
    }

    public async sleep(time: number = 0) {
        let timeout = () => new Promise((resolve) => {
            setTimeout(resolve, time);
        });
        await timeout();
    }

    public async render(time: number = 0) {
        let timeout = () => new Promise((resolve) => {
            setTimeout(resolve, time);
        });
        if (time > 0) {
            this.app.ref.detectChanges();
            await timeout();
        }
        this.app.ref.detectChanges();
    }

    public href(url: any) {
        this.app.router.navigateByUrl(url);
    }

    public random(stringLength: number = 16) {
        const fchars = 'abcdefghiklmnopqrstuvwxyz';
        const chars = '0123456789abcdefghiklmnopqrstuvwxyz';
        let randomstring = '';
        for (let i = 0; i < stringLength; i++) {
            let rnum = null;
            if (i === 0) {
                rnum = Math.floor(Math.random() * fchars.length);
                randomstring += fchars.substring(rnum, rnum + 1);
            } else {
                rnum = Math.floor(Math.random() * chars.length);
                randomstring += chars.substring(rnum, rnum + 1);
            }
        }
        return randomstring;
    }
}

export default Service;