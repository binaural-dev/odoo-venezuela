/** @odoo-module **/

import { registry } from "@web/core/registry";
import { becomeSuperuser } from "@web/core/debug/debug_menu_items";

registry.category("debug").category("default").remove("becomeSuperuser", becomeSuperuser);
