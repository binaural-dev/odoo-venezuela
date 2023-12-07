/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { ListRenderer } from "@web/views/list/list_renderer";
import { useService } from "@web/core/utils/hooks";
import { KanbanRenderer } from '@web/views/kanban/kanban_renderer';
import { useSubEnv, useState, useRef, useEffect } from "@odoo/owl";
import { FormController } from "@web/views/form/form_controller";
import { registry } from "@web/core/registry";
const {
        onMounted,
        onPatched,
        onWillStart,
        onWillUpdateProps,
    } = owl;



let session = require('web.session');

let create_group = false;
let edit_group = false;
let export_group = false;
let export_group_btn = false;
let admin_group = false;


let def_create = session.user_has_group('bi_advance_hide_show_menu.group_create_btn_access').then(function (has_create_group) {
    create_group = has_create_group;
});

let def_edit = session.user_has_group('bi_advance_hide_show_menu.group_edit_form_btn_access').then(function (has_edit_group) {
    edit_group = has_edit_group;
});

let def_export_action = session.user_has_group('bi_advance_hide_show_menu.group_hide_export_action').then(function (has_export_action_group) {
    export_group = has_export_action_group;
});

let def_export_btn = session.user_has_group('bi_advance_hide_show_menu.group_export_btn_access').then(function (has_export_btn_group) {
    export_group_btn = has_export_btn_group;
});




let def_usergroup = session.user_has_group('base.group_system').then(function (has_duplicate_group) {
    admin_group = has_duplicate_group;
});


export const patchListControllerHideButtons = {

    setup() {
            this._super();
            if(create_group == true && !admin_group  && this.activeActions.create){
    //      
                    this.has_create_group = false;
                    this.activeActions.create = false;
                }
                if(export_group_btn == true   && this.activeActions.exportXlsx){
                    this.activeActions.exportXlsx=false
                }
            
            //this.actionActions.exportXlsx=false
        },
};
export const patchKanbanRendererHideButton = {
    setup() {
            this._super();
            if(create_group == true && !admin_group){
                    this.has_create_group = false;
                    this.props.archInfo.activeActions.create = false;
                }
            
            
        },
        
};


export const patchFormControllerHideButtons = {
    setup() {
            
            
            
                if(create_group == true && !admin_group){
                    this.has_create_group = false;
                    this.props.archInfo.activeActions.create = false;
                }
                if(edit_group == true && !admin_group){
                    this.props.archInfo.activeActions.edit = false;
                }
                
            
            
            useSubEnv({ group_admin: admin_group });
            this._super();
        },
        
};




patch(ListRenderer.prototype, "bi_advance_hide_show_menu.patchListControllerHideButtons", patchListControllerHideButtons);
patch(KanbanRenderer.prototype, "bi_advance_hide_show_menu.patchKanbanRendererHide", patchKanbanRendererHideButton);
patch(FormController.prototype, "bi_advance_hide_show_menu.patchFormControllerHideButtons", patchFormControllerHideButtons);

