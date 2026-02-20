import moment from "moment";

export default class Formatter {
    constructor() { }

    public date(date, text) {
        if (!text) text = "-";
        if (!date) return text;
        let res = moment(date).format("YYYY-MM-DD");
        if (res == 'Invalid date') return text;
        return res;
    }

    public currency(number, isString = true) {
        if (!number) return "-";
        if (isString) {
            let num = number.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
            return num + "원";
        }

        const units = ['', '만', '억', '조', '경'];
        const parts = [];
        let remaining = number;

        for (let i = units.length - 1; i >= 0; i--) {
            const unit = Math.pow(10000, i);
            const part = Math.floor(remaining / unit);
            remaining = remaining % unit;

            if (part > 0) {
                parts.push(part + units[i]);
            }
        }

        if (remaining > 0) {
            parts.push(remaining);
        }
        if (parts.length == 0) return '-';
        return parts.join(' ') + '원';
    }

}