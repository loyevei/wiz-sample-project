import Service from '../service';

export default class Event {
    public value: any = {};

    constructor(public service: Service) { }

    public bind(name: string, fn: any) {
        if (!this.value[name]) this.value[name] = [];
        this.value[name].push(fn);
    }

    public unbind(name: string, fn: any) {
        if (!this.value[name]) return;
        this.value[name].remove(fn);
    }

    public clear(name: string) {
        if (!this.value[name]) return;
        delete this.value[name];
    }

    public async call(name: string) {
        if (!this.value[name]) return;
        for (let i = 0; i < this.value[name].length; i++)
            await this.value[name][i]();
    }

}