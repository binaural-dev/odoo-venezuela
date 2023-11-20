/** @odoo-module **/


import PosComponent from "point_of_sale.PosComponent";
import Registries from "point_of_sale.Registries";

import { useRef } from "@odoo/owl";
import { nextFrame } from "point_of_sale.utils";

export class DeliveryCommandScreen extends PosComponent {
  setup() {
    super.setup();
    this.currentOrder = this.env.pos.get_order();
    this.backScreen = this.props.goBack;
    this.command = useRef("delivery-command");
    this.foreignCommand = useRef("delivery-command-foreign");
  }
  get currency() {
    return this.env.pos.currency;
  }
  get foreignCurrency() {
    return this.env.pos.foreign_currency;
  }
  goBack() {
    this.showScreen(this.backScreen, { reuseSavedUIState: true });
  }
  async retryReport() {
    await this._printDeliveryCommand(this.command);
  }
  async retryForeignReport() {
    await this._printDeliveryCommand(this.foreignCommand);
  }
  async _printDeliveryCommand(commandRef) {
    if (this.env.proxy.printer) {
        const printResult = await this.env.proxy.printer.print_receipt(commandRef.el.innerHTML);
        if (printResult.successful) {
            return true;
        } else {
            await this.showPopup('ErrorPopup', {
                title: printResult.message.title,
                body: printResult.message.body,
            });
            const { confirmed } = await this.showPopup('ConfirmPopup', {
                title: printResult.message.title,
                body: 'Do you want to print using the web printer?',
            });
            if (confirmed) {
                // We want to call the _printWeb when the popup is fully gone
                // from the screen which happens after the next animation frame.
                await nextFrame();
                return await this._printWeb();
            }
            return false;
        }
    } else {
        return await this._printWeb();
    }
  }
  async _printWeb() {
    try {
        window.print();
        return true;
    } catch (_err) {
        await this.showPopup('ErrorPopup', {
            title: this.env._t('Printing is not supported on some browsers'),
            body: this.env._t(
                'Printing is not supported on some browsers due to no default printing protocol ' +
                    'is available. It is possible to print your tickets by making use of an IoT Box.'
            ),
        });
        return false;
    }
  }
};
DeliveryCommandScreen.template = "DeliveryCommandScreen";

Registries.Component.add(DeliveryCommandScreen);
