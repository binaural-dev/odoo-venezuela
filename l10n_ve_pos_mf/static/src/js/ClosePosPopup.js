odoo.define("l10n_ve_pos_mf.ClosePosPopup", function(require) {
  "use strict";

  const ClosePosPopup = require("point_of_sale.ClosePosPopup");
  const Registries = require("point_of_sale.Registries");
  const { Gui } = require("point_of_sale.Gui");

  const BinauralClosePosPopup = (ClosePosPopup) =>
    class extends ClosePosPopup {
      generate_report_x() {
        const fdm = this.env.pos.useFiscalMachine();
        if (!fdm) return;
        new Promise(async (resolve, reject) => {
          await fdm.action({
            action: "report_x",
            data: {},
          });
        });
      }
      async generate_report_z() {
        console.log("Initiating Z Report generation");
        const fiscalDeviceManager = this.env.pos.useFiscalMachine();

        if (!fiscalDeviceManager) {
          console.error("Fiscal device manager not available");
          return;
        }

        try {
          const fiscalResponse =
            await this.executeFiscalReportZ(fiscalDeviceManager);
          console.log("Primer manejo de erorr");

          // 2. Enviar datos al backend
          await this.submitZReportToAccounting(fiscalResponse.value);

          // 3. Actualizar sesión POS
          await this.updatePosSession(fiscalResponse.value);
        } catch (error) {
          console.log("Z Report generation failed:", error.message);
          if (!error.valid) {
            console.log("Error");
            return {
              code: 700,
              data: {
                error: {
                  status: error.message
                    ? error.message
                    : "Error de Conexion con la Maquina Fiscal #1",
                },
              },
            };
          } else {
            // other errors
            return {
              code: 700,
              data: {
                error: {
                  status: error.status
                    ? error.status
                    : "Error de Conexion con la Maquina Fiscal #2",
                },
              },
            };
          }
        }
        return;
      }

      async executeFiscalReportZ(fdm) {
        console.log("Ejecutado");
        return new Promise((resolve, reject) => {
          const handleFiscalResponse = (data) => {
            try {
              fdm.remove_listener(handleFiscalResponse);

              const { value } = data;
              if (data.status?.status === "connected") {
                resolve(data);
              } else {
                throw value;
              }
            } catch (error) {
              if (!error.valid) {
                return Gui.showPopup("ErrorPopup", {
                  title: error.message,
                });
              } else {
                return Gui.showPopup("ErrorPopup", {
                  title: error.message,
                });
              }
            }
          };

          fdm.add_listener(handleFiscalResponse);

          fdm.action({ action: "report_z", data: {} }).catch((error) => {
            fdm.remove_listener(handleFiscalResponse);
            reject(new Error(`Error en acción report_z: ${error.message}`));
          });
        });
      }

      async submitZReportToAccounting(zReportValue) {
        const serialMachine = this.env.pos.config.serial_machine;

        if (!serialMachine) {
          throw new Error("Número de serie del dispositivo no configurado");
        }

        await this.rpc({
          model: "account.move",
          method: "report_z",
          args: [[], serialMachine, zReportValue],
        });
      }

      async updatePosSession(zReportValue) {
        const sessionId = this.env.pos.pos_session?.id;

        if (!sessionId) {
          throw new Error("Sesión POS no disponible");
        }

        await this.rpc({
          model: "pos.session",
          method: "set_report_z",
          args: [sessionId, zReportValue],
        });
      }
    };

  Registries.Component.extend(ClosePosPopup, BinauralClosePosPopup);
  return ClosePosPopup;
});
