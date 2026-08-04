/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { ProjectRightSidePanel } from "@project/components/project_right_side_panel/project_right_side_panel";

/**
 * Patch the ProjectRightSidePanel prototype to extend panel behavior.
 * Example: modify getters or methods that control panel visibility / data.
 */
patch(ProjectRightSidePanel.prototype, {
    /**
     * Example getter override (uncomment and adapt when needed):
     *
     * get panelVisible() {
     *     return super.panelVisible || this.state.data.show_l10n_ve_project_items;
     * }
     */
});
