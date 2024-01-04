
odoo.define("binaural_megasoft.ClosePosPopup", function (require) {
  'use strict';

  const ClosePosPopup = require('point_of_sale.ClosePosPopup');
  const Registries = require('point_of_sale.Registries');
  var Session = require("web.Session");


  const BinauralClosePosPopup = (ClosePosPopup) =>
    class extends ClosePosPopup {
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
