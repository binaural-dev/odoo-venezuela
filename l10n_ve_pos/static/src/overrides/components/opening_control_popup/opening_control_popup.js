/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { OpeningControlPopup } from "@point_of_sale/app/components/popups/opening_control_popup/opening_control_popup";

patch(OpeningControlPopup.prototype, {
  /**
   * El popup abre la sesión sin recargar los datos: una caja cargada antes
   * (la noche anterior, otra pestaña) abriría con la tasa que tiene en el
   * navegador. Antes de abrir se compara con la tasa de la sesión
   * (PosStore.checkOpeningRate); si no es la misma, la caja no abre y recarga
   * sus datos. Lo que otros módulos registran al abrir va en
   * _beforeOpeningSession, después del chequeo, para no dejarlo hecho en una
   * caja que no abrió.
   */
  async confirm() {
    const check = await this.pos.checkOpeningRate();
    if (check === "blocked") {
      return;
    }
    await this._beforeOpeningSession();
    const res = await super.confirm(...arguments);
    if (this.pos.session.state !== "opened") {
      return res;
    }
    if (check === "reload") {
      await this.pos.reloadData(true);
      return res;
    }
    await this.pos.loadSessionRateDate();
    return res;
  },

  /**
   * Gancho: lo que se registra al abrir la sesión antes del core (p. ej. el
   * cajón en divisa de binaural_pos_close). Corre solo si la tasa es la de la
   * sesión.
   */
  async _beforeOpeningSession() {},
});
