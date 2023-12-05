/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { useSubEnv, useState, useRef, useEffect } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { ActionMenus } from "@web/search/action_menus/action_menus";
const {
        onMounted,
        onPatched,
        onWillStart,
        onWillUpdateProps,
    } = owl;




// const favoriteMenuRegistry = registry.category("favoriteMenu");
// favoriteMenuRegistry.remove("import-menu");

let session = require('web.session');

let export_group = false;
let delete_group = false;
let print_group = false;
let duplicate_group = false;
let action_group = false;
let export_group_btn=false;
var def_print = session.user_has_group('bi_advance_hide_show_menu.group_hide_print_btn').then(function (has_print_group) {
    print_group = has_print_group;
});
var def_action = session.user_has_group('bi_advance_hide_show_menu.group_hide_action_btn').then(function (has_action_group) {
     action_group = has_action_group;
});
let def_export_action = session.user_has_group('bi_advance_hide_show_menu.group_hide_export_action').then(function (has_export_action_group) {
    export_group = has_export_action_group;
});
let def_export_btn = session.user_has_group('bi_advance_hide_show_menu.group_export_btn_access').then(function (has_export_btn_group) {
    export_group_btn = has_export_btn_group;
});
let def_delete = session.user_has_group('bi_advance_hide_show_menu.group_hide_delete_action').then(function (has_delete_group) {
    delete_group = has_delete_group;
});
let def_duplicate = session.user_has_group('bi_advance_hide_show_menu.group_hide_duplicate_action').then(function (has_duplicate_group) {
    duplicate_group = has_duplicate_group;
});



export const patchActionMenu = {
    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        onWillStart(async () => {
            this.actionItems = [];
            if (action_group == true){
                this.actionItems.length = 0;
            }else{
                this.actionItems = await this.setActionItems(this.props);
            }
            
        });
        onWillUpdateProps(async (nextProps) => {
            this.actionItems = [];
            if (action_group == true){
                this.actionItems.length = 0;
            }else{
                this.actionItems = await this.setActionItems(nextProps);
            }
            
        });
    },
    get printItems() {
        var printActions = this.props.items.print || [];
        if(print_group == true){
            printActions.length=0
        }
        return printActions.map((action) => ({
            action,
            description: action.name,
            key: action.id,
        }));
    },
    async setActionItems(props) {
        
        // Callback based actions
        var callbackActions = (props.items.other || []).map((action) =>
            Object.assign({ key: `action-${action.description}` }, action)
        );
        var remove_index=[]
        for(var i=0; i<callbackActions.length;i++){
            if(callbackActions[i].key == 'export'){
                if(export_group == true || export_group_btn == true){
                    remove_index.push(i)
                    // callbackActions.splice(i, 1);
                }
            }
            if(callbackActions[i].key == 'delete'){
                if(delete_group == true){
                    remove_index.push(i)
                    // callbackActions.splice(i, 1);
                }
            }
            if(callbackActions[i].key == 'duplicate'){
                if(duplicate_group == true){
                    remove_index.push(i)
                
            }
        }
        }
        for (var i = remove_index.length -1; i >= 0; i--){
            callbackActions.splice(remove_index[i], 1);
        }
        const actionActions = props.items.action || [];
        const formattedActions = actionActions.map((action) => ({
            action,
            description: action.name,
            key: action.id,
        }));
        // ActionMenus action registry components
        const registryActions = [];
        for (const { Component, getProps } of registry.category("action_menus").getAll()) {
            const itemProps = await getProps(props, this.env);
            if (itemProps) {
                registryActions.push({
                    Component,
                    key: `registry-action-${registryActionId++}`,
                    props: itemProps,
                });
            }
        }
        return [...callbackActions, ...formattedActions, ...registryActions];
    }

    }





patch(ActionMenus.prototype, "bi_advance_hide_show_menu.patchActionMenu", patchActionMenu);
