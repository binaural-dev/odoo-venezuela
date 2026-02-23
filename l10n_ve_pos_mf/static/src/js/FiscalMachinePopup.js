/** @odoo-module **/

import { Component } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

export class FiscalMachinePopup extends Component {
  static template = "binaural_pos_mf.FiscalMachinePopup";
  static defaultProps = {
    cancelText: _t("Cancel"),
    title: _t("Fiscal Reports"),
  };

  setup() {
    this.ui = useService("ui");
    this.orm = useService("orm");
  }

  async report_z() {
    const pos = this.env.pos;
    const fdm = pos?.useFiscalMachine?.();
    if (!fdm) {
      this.props.close({ confirmed: false, error: _t("No fiscal machine configured") });
      return;
    }

    this.ui.block();
    try {
      const start = await fdm.action({ action: "report_z", data: {} });
      if (!start?.result) {
        throw new Error(_t("Cannot connect to the fiscal machine"));
      }

      const data = await new Promise((resolve, reject) => {
        const listener = (evt) => {
          if (evt?.request_data?.action !== "report_z") return;
          fdm.removeListener(listener);
          if (evt?.value?.valid) {
            resolve(evt.value);
          } else {
            reject(evt?.value || { message: _t("Unknown fiscal machine error") });
          }
        };
        fdm.addListener(listener);
      });

      await this.orm.call("account.move", "report_z", [[], pos.config.serial_machine, data]);
      await this.orm.call("pos.session", "set_report_z", [pos.pos_session.id, data]);

      this.props.close({ confirmed: true, payload: data });
    } catch (e) {
      this.props.close({
        confirmed: false,
        error: e?.message || e?.status || _t("Internal MF error"),
      });
    } finally {
      this.ui.unblock();
    }
  }

  async report_x() {
    const pos = this.env.pos;
    const fdm = pos?.useFiscalMachine?.();
    if (!fdm) {
      this.props.close({ confirmed: false, error: _t("No fiscal machine configured") });
      return;
    }

    this.ui.block();
    try {
      await fdm.action({ action: "report_x", data: {} });
      this.props.close({ confirmed: true });
    } catch (e) {
      this.props.close({
        confirmed: false,
        error: e?.message || e?.status || _t("Internal MF error"),
      });
    } finally {
      this.ui.unblock();
    }
  }
}
