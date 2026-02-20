import Service from '../service';

export default class Modal {

    public isshow: boolean = false;
    public callback: any = null;
    public hide: any = async () => { };
    public action: any = async () => { };
    public default_opts: any = {
        title: 'Are you sure?',
        message: "Do you really want to remove app? What you've done cannot be undone.",
        action: "Delete",
        actionBtn: "error",
        cancel: true,
        status: 'error'
    };
    public opts: any = {};

    constructor(private service: Service) { }

    public async show(mopts: any = {}) {
        this.isshow = true;
        this.opts = JSON.parse(JSON.stringify(this.default_opts));
        for (let key in mopts)
            this.opts[key] = mopts[key];
        await this.service.render();

        let fn = () => new Promise((resolve) => {
            this.cancel = async () => {
                this.isshow = false;
                await this.service.render();
                resolve(false);
            }

            this.hide = async () => {
                this.isshow = false;
                await this.service.render();
                resolve();
            }

            this.action = async (data: any = true) => {
                this.isshow = false;
                await this.service.render();
                resolve(data);
            }
        });

        return await fn();
    }

    public async error(message: string, cancel: any = false, action: string = 'OK') {
        return await this.show({
            title: "",
            message: message,
            cancel: cancel,
            actionBtn: 'error',
            action: action,
            status: 'error'
        });
    }

    public async success(message: string, cancel: any = false, action: string = 'OK') {
        return await this.show({
            title: "",
            message: message,
            cancel: cancel,
            actionBtn: 'success',
            action: action,
            status: 'success'
        });
    }

    public async warning(message: string, cancel: any = false, action: string = 'OK') {
        return await this.show({
            title: "",
            message: message,
            cancel: cancel,
            actionBtn: 'warning',
            action: action,
            status: 'warning'
        });
    }

    public localize(mopts: any = {}) {
        let modal = new Modal(this.service);
        for (let key in mopts)
            modal.default_opts[key] = mopts[key];
        return modal;
    }

}