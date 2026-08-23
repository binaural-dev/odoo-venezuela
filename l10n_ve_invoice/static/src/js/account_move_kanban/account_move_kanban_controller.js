/** @odoo-module **/

import { AccountMoveKanbanController } from '@account/views/account_move_kanban/account_move_kanban_controller';
import { patch } from '@web/core/utils/patch';

patch(AccountMoveKanbanController.prototype, {
    setup() {
        super.setup();
        if (this.props.context?.no_upload) {
            this.showUploadButton = false;
        }
    },
});
