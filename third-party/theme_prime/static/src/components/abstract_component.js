/** @odoo-module */
const { Component } = owl;
import { useService } from '@web/core/utils/hooks';
import { registry } from '@web/core/registry';
import { useCore } from '@droggol_theme_common/js/hooks';

export class CoreComponent extends Component {
    setup() {
        super.setup();
        if (this._coreProps){
            useCore({});
        }
        if (this._coreCProps){
            useCore({core: this._coreCProps, subMode: true});
        }
    }
    getOWLComponent(name) {
        return registry.category('theme_components').get(name);
    }
    getRecord(records, value, key) {
        key = key ? key : 'id';
        return records.find((record) => record[key] === value);
    }
}

export class AbstractComponent extends CoreComponent {
    setup() {
        this.componentService = useService('shared_component_service');
        super.setup();
    }
    get currentSubCoreComponents() {
        let components = [];
        this.supportedComponents.forEach((component, name) => {
            components.push({ ...this.prepareComponentValues(component) })
        });
        let filtered = components.filter(el => Object.keys(el).length);
        return filtered;
    }
    prepareComponentValues(name) {
        let componentValue = {};
        for (const comp in this.componentRegistry) {
            if (this.componentRegistry[comp].includes(name) && this.nodeOptions[name]) {
                componentValue = { component: comp, name: name, value: this.componentDefaultVal[name], ...this.nodeOptions[name] }
            }
        }
        return componentValue;
    }
    getSubComponent(name) {
        return this.getRecord(this.currentSubCoreComponents, name, 'name');
    }
}