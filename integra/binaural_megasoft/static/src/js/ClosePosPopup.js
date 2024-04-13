
odoo.define("binaural_megasoft.ClosePosPopup", function (require) {
  'use strict';

  const ClosePosPopup = require('point_of_sale.ClosePosPopup');
  const Registries = require('point_of_sale.Registries');
  var Session = require("web.Session");


  const BinauralClosePosPopup = (ClosePosPopup) =>
    class extends ClosePosPopup {
      async pre_close_pdv() {
        const fdm = this.env.pos.useFiscalMachine();
        if (!fdm) return
        this.rpc({ "model": "pos.session", "method": "get_total_payments", "args": [this.env.pos.config.current_session_id[0]] })
          .then((data) => {
            fdm.action({
              action: 'logger_multi',
              data: [
                "800REPORTE DE VENTAS",
                `800CAJA: ${this.env.pos.config.current_session_id[1]}`,
                `800HORA: ${moment().format('YYYY-MM-DD hh:mm A')}`,
                "800-----------------------------",
                "800DETALLES",
                `800COMPRAS              ${data["payments"]} VES`,
                "810"],
            })
          })
      }
      async close_pdv() {
        let connection = new Session(undefined, "http://localhost:8069", {
          use_cors: true,
        });
        connection.rpc("/megasoft/cierre", {
          data: {
            megasoft_data:{
              accion: "cierre",
            },
            url: this.env.pos.company.url_megasoft,
            port: this.env.pos.company.port_megasoft
          }
        }).then((data) => {
          console.log(data)
        })
      }
    }

  Registries.Component.extend(ClosePosPopup, BinauralClosePosPopup);
  return ClosePosPopup
})
