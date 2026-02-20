import Service from '../service';

export default class Status {

    constructor(private service: Service) { }

    public async toggle(target: string, status: any = null) {
        if (status === null) {
            this[target] = !this[target];
        } else {
            this[target] = status;
        }
        await this.service.render();
    }

    public async show(target: string) {
        this[target] = true;
        await this.service.render();
    }

    public async hide(target: string) {
        this[target] = false;
        await this.service.render();
    }
}