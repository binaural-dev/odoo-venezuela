/** @odoo-module **/

import { registry } from "@web/core/registry";
import { ThemeConfigDialog } from '../components/theme_config';

registry.category('website_custom_menus').add('droggol_theme_common.menu_theme_prime_config', {
    Component: ThemeConfigDialog,
    isDisplayed: (env) => !!env.services.website.currentWebsite
        && env.services.website.isDesigner
});
