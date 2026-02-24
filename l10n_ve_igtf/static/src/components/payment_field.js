/** @odoo-module **/

import { AccountPaymentField } from "@account/components/account_payment_field/account_payment_field";
import { patch } from "@web/core/utils/patch";

patch(AccountPaymentField.prototype, {
  setup() {
    super.setup();
  },
  async removeMoveReconcile(moveId, partialId) {
    this.popover.close();
    let wizard = false;
    wizard = await this.orm.call(
      this.props.record.resModel,
      "js_remove_outstanding_partial",
      [moveId, partialId],
      {},
    );
    if (wizard && typeof wizard === "object") {
      this.action.doAction(wizard);
    }
    await this.props.record.model.root.load();
  },
});