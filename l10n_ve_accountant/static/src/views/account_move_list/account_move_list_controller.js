/** @odoo-module **/

import { AccountMoveListController } from '@account/views/account_move_list/account_move_list_controller';
import { patch } from '@web/core/utils/patch';

patch(AccountMoveListController.prototype, {
    setup() {
        super.setup();
        if (this.props.context?.no_upload) {
            this.showUploadButton = false;
        }
    },
});
