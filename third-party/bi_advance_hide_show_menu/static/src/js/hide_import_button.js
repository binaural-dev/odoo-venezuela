/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { useSubEnv, useState, useRef, useEffect } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { ImportRecords } from "@base_import/import_records/import_records";
const {
        onMounted,
        onPatched,
        onWillStart,
        onWillUpdateProps,
    } = owl;




// const favoriteMenuRegistry = registry.category("favoriteMenu");
// favoriteMenuRegistry.remove("import-menu");

let session = require('web.session');

let import_group = false;



var def_import = session.user_has_group('bi_advance_hide_show_menu.group_import_btn_access').then(function (has_import_group) {
                   import_group = has_import_group;
                   });


export const patchImportMenuHide = {
    setup() {
        this.action = useService("action");
        if (import_group==true){
            this.hasimportmenu=false
        }
        else{
            this.hasimportmenu=true
        }

    }
}


patch(ImportRecords.prototype, "bi_advance_hide_show_menu.patchImportMenuHide", patchImportMenuHide);
