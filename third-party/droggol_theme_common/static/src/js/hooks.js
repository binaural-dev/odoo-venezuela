/** @odoo-module **/

import { useComponent, useChildSubEnv} from "@odoo/owl";

// We add here a custom hook
function extendUseCore(cc, newCore, subMode) {
    if (!subMode) {
        const currentCore = Object.create(cc.env);
        const newCoreDescriptors = Object.getOwnPropertyDescriptors(newCore);
        cc.env = Object.freeze(Object.defineProperties(currentCore, newCoreDescriptors));
    }
    useChildSubEnv(newCore)
}

export function useCore({core = false, subMode = false}) {
    const cc = useComponent();
    core = core || cc._coreProps;
    if (core) {
        extendUseCore(cc, core, subMode)
    }
}