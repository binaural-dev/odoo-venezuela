/** @odoo-module */
import PaymentScreen from "point_of_sale.PaymentScreen";
import Registries from "point_of_sale.Registries";

var Session = require("web.Session");

const BinauralPaymentScreen = (PaymentScreen) =>
  class BinauralPaymentScreen extends PaymentScreen {


    async megasoftPing() {
      let connection = new Session(undefined,"http://localhost:8069", {
        use_cors: true,
      });
      connection.rpc("megasoft/ping", {
        data: {
          url: this.env.pos.company.url_megasoft,
          port: this.env.pos.company.port_megasoft
        },
      }).then((data) => {
        console.log(data)
      })
    }

    async megasoftCambio() {
      let due = (this.env.pos.foreign_currency.id === 3 ? this.selectedPaymentLine.foreign_amount : this.selectedPaymentLine.amount)
      if (this.selectedPaymentLine.payment_method.is_change) {
        let connection = new Session(undefined,"http://localhost:8069", {
          use_cors: true,
        });

        if (!this.env.pos.get_order().get_partner()){
          return this.showPopup("ErrorPopup", {
            title: this.env._t("No hay partner seleccionado"),
            body: this.env._t(
              "Seleccionar un partner"
            ),
          });
        }

        connection.rpc("/megasoft/cambio", {
          data: {
            megasoft_data: {
              accion: "cambio",
              montoTransaccion: parseInt(-due * 100),
              cedula: this.env.pos.get_order().get_partner().vat,
              tipoMoneda: "VES",
            },
            url: this.env.pos.company.url_megasoft,
            port: this.env.pos.company.port_megasoft
          },
        }).then((data) => {
          console.log(data)
        })
      }
    }

    async megasoftPaymentPdv() {
      let amount = (this.env.pos.foreign_currency.id === 3 ? this.selectedPaymentLine.foreign_amount : this.selectedPaymentLine.amount)
      if (this.selectedPaymentLine.payment_method.is_payment_pdv) {
        let connection = new Session(undefined,"http://localhost:8069", {
          use_cors: true,
        });

        if (!this.env.pos.get_order().get_partner()){
          return this.showPopup("ErrorPopup", {
            title: this.env._t("No hay partner seleccionado"),
            body: this.env._t(
              "Seleccionar un partner"
            ),
          });
        }

        connection.rpc("/megasoft/pago", {
          data: {
            megasoft_data: {
              accion: "tarjeta",
              montoTransaccion: parseInt(amount * 100),
              cedula: this.env.pos.get_order().get_partner().vat,
            },
            url: this.env.pos.company.url_megasoft,
            port: this.env.pos.company.port_megasoft
          },

        }).then((data) => {

          if (data.codRespuesta === 'BN'){ //Codigo de tiempo expirado
            return this.showPopup("ErrorPopup", {
              title: this.env._t("Tiempo expirado"),
              body: this.env._t(
                "El tiempo para realizar la transaccion expiró"
              ),
            });
          }    
        })
        .catch(data => console.log(data))
      }
    }

    async megasoftPaymentP2c() {
      let amount = (this.env.pos.foreign_currency.id === 3 ? this.selectedPaymentLine.foreign_amount : this.selectedPaymentLine.amount)

      if (this.selectedPaymentLine.payment_method.is_payment_p2c) {
        let connection = new Session(undefined,"http://localhost:8069", {
          use_cors: true,
        });

        if (!this.env.pos.get_order().get_partner()){
          return this.showPopup("ErrorPopup", {
            title: this.env._t("No hay partner seleccionado"),
            body: this.env._t(
              "Seleccionar un partner"
            ),
          });
        }
        connection.rpc("/megasoft/pago", {
          data: {
            megasoft_data: {
              accion: "tarjeta",
              montoTransaccion: parseInt(amount * 100),
              cedula: this.env.pos.get_order().get_partner().vat,
            },
            url: this.env.pos.company.url_megasoft,
            port: this.env.pos.company.port_megasoft
          },

        }).then((data) => {
          console.log(data)
          if (data.codRespuesta === 'AM'){ //Codigo de tiempo expirado
            return this.showPopup("ErrorPopup", {
              title: this.env._t("Tiempo expirado"),
              body: this.env._t(
                "El tiempo para realizar la transaccion expiró"
              ),
            });
          }    
        })
      }
    }

    async megasoftUltimaTransaccionAprobada() {
      let connection = new Session(undefined,"http://localhost:8069", {
        use_cors: true,
      });

      connection.rpc("/megasoft/ultimaTransaccionAprobada", {
        data: {
          megasoft_data: {
            accion: "imprimeUltimoVoucher",
          },
          url: this.env.pos.company.url_megasoft,
          port: this.env.pos.company.port_megasoft
        },
      }).then((data) => {
        console.log(data)
      })

    }

    async megasoftUltimaTransaccionProcesada() {
      let connection = new Session(undefined,"http://localhost:8069", {
        use_cors: true,
      });
      console.log(connection)

      connection.rpc("/megasoft/ultimaTransaccionProcesada", {
        data: {
          megasoft_data: {
            accion: "imprimeUltimoVoucherP",
          },
          url: this.env.pos.company.url_megasoft,
          port: this.env.pos.company.port_megasoft
        },
      }).then((data) => {
        console.log(data)
      })

    }


  };

Registries.Component.extend(PaymentScreen, BinauralPaymentScreen);
