/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { SelfOrder } from "@pos_self_order/app/services/self_order_service";
import { rpc } from "@web/core/network/rpc";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";
import { TfhkaDriver } from "@l10n_ve_mf_base/drivers/TfhkaDriver";
import { buildKioskFiscalPayload } from "@l10n_ve_pos_mf_self_order/app/fiscal_payload";

/**
 * Conexión a la máquina fiscal (TFHKA, Web Serial) en el Kiosko/Autopedido.
 *
 * El Kiosko es DESATENDIDO: a diferencia de la caja (que trae un botón visible
 * `FiscalPrinterButton` en el navbar), aquí no hay botón de cara al cliente.
 * Web Serial es EXCLUSIVO por puerto (una sola pestaña/app puede tenerlo
 * abierto a la vez), así que el Kiosko conecta "bajo demanda": al arrancar
 * solo verifica que el puerto siga PAREADO (`isPaired`, consulta
 * `navigator.serial.getPorts()` sin abrirlo — no reserva el puerto ni compite
 * con otro consumidor), y recién abre la conexión real justo antes de cada
 * impresión/reimpresión, cerrándola de nuevo al terminar (ver
 * `printKioskFiscalInvoice`/`reprintKioskFiscalCopy`/
 * `_releaseFiscalPrinterConnection`). El pareo inicial manual
 * (`requestPermission`, que sí exige un gesto) queda bajo modo debug.
 *
 * Se reutiliza el MISMO driver que la caja (`window.fiscalPrinter`, singleton
 * global del navegador): si el kiosko y un POS de caja conviven en el mismo
 * navegador, comparten la conexión (nunca simultáneamente, por el modelo
 * bajo demanda).
 */
patch(SelfOrder.prototype, {
    setup() {
        super.setup(...arguments);
        // Estado reactivo para el overlay "Espere mientras se imprime su
        // factura" (self_order_index_fiscal.xml), leído desde la raíz del
        // Kiosko para cubrir cualquier pantalla (la impresión ocurre ya en
        // confirmationPage, ver más abajo).
        this.printingFiscalInvoice = false;
        // Órdenes con una impresión fiscal EN CURSO (por access_token), para el
        // guard de reentrada de `confirmationPage` (ver allí): el bus
        // PAYMENT_STATUS puede reentrar antes de que la impresión asíncrona
        // setee `mf_invoice_number`.
        this._fiscalPrintingOrders = new Set();
        // Solo en modo kiosko y si la caja tiene habilitada la máquina fiscal.
        // Fire-and-forget: no bloquea el arranque de la app. Solo VERIFICA el
        // pareo (sin abrir el puerto) — ver comentario de cabecera.
        if (this.kioskMode && this.config?.access_button_mf) {
            this.checkFiscalPrinterPairing();
            // Reintentar en segundo plano las persistencias de número fiscal que
            // quedaron pendientes (el papel salió pero `write_mf_invoice_data`
            // falló y se guardó localmente). NO reimprime; solo re-persiste.
            this.retryPendingFiscalPersists();
        }
    },

    /**
     * Enganche de impresión fiscal (modelo REGISTRAR-PRIMERO).
     *
     * Se imprime la factura fiscal SOLO al llegar a la confirmación, cuando la
     * orden YA está registrada y facturada en Odoo (con id de servidor). Nunca
     * antes — así jamás se emite un documento fiscal (número SENIAT) sin su
     * orden/factura en Odoo. El número resultante se persiste en el servidor
     * (orden + account.move) vía `write_mf_invoice_data`.
     *
     * `confirmationPage` es el punto genérico por el que pasan todos los pagos
     * (Megasoft/terminal → bus PAYMENT_STATUS → connectNewData → aquí). Se
     * imprime solo si la orden está pagada y aún no tiene número fiscal; el
     * pago se deriva de `order.payment_ids` (ya presentes tras el registro).
     * Fire-and-forget respecto a la navegación (no bloquea el paso a
     * confirmationPage), pero `printingFiscalInvoice` queda en true mientras
     * tanto para que el overlay (self_order_index_fiscal.xml) le avise al
     * cliente que espere — sin eso, la orden ya se ve "confirmada" en pantalla
     * mientras la máquina fiscal todavía está imprimiendo en segundo plano.
     */
    async confirmationPage(screen_mode, device, access_token) {
        const res = await super.confirmationPage(...arguments);
        if (this.kioskMode && access_token && this.config?.access_button_mf) {
            const order = this.models["pos.order"].find(
                (o) => o.access_token === access_token
            );
            if (
                order &&
                !order.mf_invoice_number &&
                // NO auto-imprimir si la factura CONTABLE de Odoo aún está
                // pendiente (`is_invoiced === false`): la orden se pagó pero su
                // facturación se difirió (ver pos.order._process_saved_order en
                // l10n_ve_pos_self_order). Queda pendiente por facturar en la
                // máquina fiscal también; se resuelve desde el panel de
                // recuperación (crear factura → imprimir fiscal). Emitir un nº
                // fiscal sin account.move donde estamparlo crearía un desfase.
                order.is_invoiced &&
                ["paid", "done", "invoiced"].includes(order.state) &&
                // Guard de reentrada: `confirmationPage` es el punto por el que
                // reentra el bus PAYMENT_STATUS, y puede hacerlo ANTES de que la
                // impresión asíncrona (fire-and-forget de abajo) setee
                // `mf_invoice_number`. Sin este guard, una segunda entrada vería
                // `!mf_invoice_number` aún true y arrancaría una SEGUNDA
                // impresión → doble documento fiscal. Se marca la orden como
                // "imprimiéndose" hasta que la promesa termine.
                !this._fiscalPrintingOrders.has(access_token)
            ) {
                this._fiscalPrintingOrders.add(access_token);
                this.printingFiscalInvoice = true;
                this.printKioskFiscalInvoice(order)
                    .then((result) => {
                        if (!result || !result.valid) {
                            console.error(
                                "[MF Kiosk] impresión fiscal en confirmación falló:",
                                result && result.message
                            );
                            this.dialog.add(AlertDialog, {
                                title: _t("Fiscal invoice not printed"),
                                body: _t(
                                    "The order was registered and invoiced. The fiscal invoice " +
                                        "could not be printed (reason: %s). It can be reprinted " +
                                        "from the MF Debug menu.",
                                    (result && result.message) || _t("unknown error")
                                ),
                            });
                        }
                    })
                    .finally(() => {
                        this.printingFiscalInvoice = false;
                        this._fiscalPrintingOrders.delete(access_token);
                    });
            }
        }
        return res;
    },

    /** @returns {TfhkaDriver|null} */
    getFiscalPrinter() {
        return window.fiscalPrinter || null;
    },

    /**
     * Refleja el estado LIVE de la conexión en memoria. En el modelo bajo
     * demanda esto es `false` casi siempre (solo `true` mientras una
     * impresión/reimpresión/pareo está en curso) — no sirve para "¿está todo
     * OK para imprimir?" en reposo. Para eso, usar `checkFiscalPrinterConnection`
     * (prueba real, conecta-verifica-libera) o `checkFiscalPrinterPairing`
     * (solo pareo, sin tocar el hardware).
     * @returns {boolean}
     */
    useFiscalMachine() {
        const printer = this.getFiscalPrinter();
        return Boolean(printer && printer.isConnected);
    },

    /**
     * Prueba real de conexión bajo demanda, pensada para el botón "Comprobar
     * estado de conexión" del modo debug: conecta, consulta el estado (ENQ) y
     * libera el puerto de inmediato — a diferencia de `useFiscalMachine`, que
     * solo lee un flag en memoria casi siempre `false` en reposo con este
     * modelo.
     * @returns {Promise<boolean>}
     */
    async checkFiscalPrinterConnection() {
        const printer = await this.ensureFiscalPrinterConnected();
        const ok = Boolean(printer && printer.isConnected);
        await this._releaseFiscalPrinterConnection(printer);
        return ok;
    },

    /**
     * Chequeo de arranque: verifica que el puerto siga PAREADO (autorizado en
     * una sesión anterior) SIN abrirlo. A diferencia de
     * `ensureFiscalPrinterConnected`, esto NO reserva el puerto — Web Serial
     * es exclusivo, así que si el Kiosko lo abriera aquí (al cargar la app y
     * quedarse así todo el turno) ningún otro consumidor (otra caja, el
     * pareo manual desde otra pestaña, el Fiscalizador del backoffice) podría
     * tomarlo hasta que la pestaña del Kiosko se cerrara. Solo crea el
     * singleton `window.fiscalPrinter` y deja un aviso en consola si no hay
     * pareo; la conexión real ocurre bajo demanda en cada impresión.
     */
    async checkFiscalPrinterPairing() {
        if (!("serial" in navigator)) {
            console.error("[MF Kiosk] Web Serial API no soportada en este navegador");
            return false;
        }
        if (!window.fiscalPrinter) {
            window.fiscalPrinter = new TfhkaDriver();
        }
        try {
            const paired = await window.fiscalPrinter.isPaired();
            if (!paired) {
                console.warn(
                    "[MF Kiosk] Máquina fiscal no pareada; parear desde el menú Debug"
                );
            }
            return paired;
        } catch (error) {
            console.error("[MF Kiosk] Error al verificar el pareo de la máquina fiscal", error);
            return false;
        }
    },

    /**
     * Conexión bajo demanda: crea el singleton si no existe y abre el puerto
     * ya autorizado (sin prompt) SOLO cuando hace falta imprimir/reimprimir.
     * Quien la llama es responsable de liberar la conexión al terminar
     * (`_releaseFiscalPrinterConnection`) — ver comentario de cabecera del
     * archivo. Espeja `FiscalPrinterButton._autoConnect` pero sin estado de
     * UI y sin mantener el puerto abierto entre operaciones.
     */
    async ensureFiscalPrinterConnected() {
        if (!("serial" in navigator)) {
            console.error("[MF Kiosk] Web Serial API no soportada en este navegador");
            return null;
        }
        try {
            if (!window.fiscalPrinter) {
                window.fiscalPrinter = new TfhkaDriver();
            }
            const printer = window.fiscalPrinter;
            if (!printer.isConnected) {
                await printer.connect();
            }
            return printer;
        } catch (error) {
            console.error("[MF Kiosk] Error en auto-conexión de la máquina fiscal", error);
            return null;
        }
    },

    /**
     * Pareo inicial manual (modo debug): pide permiso para elegir el puerto
     * serial (prompt del navegador — requiere gesto del usuario) y verifica
     * que responda. La AUTORIZACIÓN del puerto (lo que le permite a
     * `ensureFiscalPrinterConnected` reconectar sin prompt después) es
     * independiente de mantenerlo abierto — persiste aunque se cierre la
     * conexión — así que se libera el puerto al terminar la verificación,
     * igual que cualquier otra operación puntual del Kiosko. Sin esto, hacer
     * el pareo desde el modo debug dejaba el puerto tomado hasta la próxima
     * impresión, bloqueando a otros consumidores (otra pestaña/caja) mientras
     * tanto.
     */
    async pairFiscalPrinter() {
        if (!("serial" in navigator)) {
            console.error("[MF Kiosk] Web Serial API no soportada en este navegador");
            return false;
        }
        if (!window.fiscalPrinter) {
            window.fiscalPrinter = new TfhkaDriver();
        }
        const printer = window.fiscalPrinter;
        try {
            const connected = await printer.connect({ requestPermission: true });
            if (connected) {
                const status = await printer.getStatus();
                printer.isConnected = Boolean(status);
            }
            return printer.isConnected;
        } finally {
            await this._releaseFiscalPrinterConnection(printer);
        }
    },

    /**
     * Imprime la factura fiscal de la orden del Kiosko en la máquina (TFHKA).
     *
     * Client-side puro: arma el payload desde la orden en memoria y lo manda al
     * driver, sin RPC al servidor. El número fiscal devuelto se guarda en la
     * orden (viaja al servidor al sincronizar vía `_load_pos_self_data_fields`).
     *
     * Idempotente: si la orden ya tiene `mf_invoice_number`, no reimprime (mismo
     * criterio que la caja, `!order.mf_invoice_number`).
     *
     * @param {Object} order  la orden del Kiosko (selfOrder.currentOrder)
     * @param {Object} opts   { paymentMethod (pos.payment.method), amount (VES) }
     * @returns {Promise<{valid:boolean, message?:string, response?:Object}>}
     */
    async printKioskFiscalInvoice(order, { paymentMethod, amount } = {}) {
        if (order.mf_invoice_number) {
            return { valid: true, message: "", alreadyPrinted: true };
        }

        // Reimpresión: si no se pasa el pago explícito (flujo en vivo), derivarlo
        // de la orden YA registrada (sus `payment_ids` ya están en el cliente
        // tras sincronizar). El monto se toma en la moneda de la orden; en este
        // despliegue la moneda base es la fiscal (VES), así que no se convierte.
        if (!paymentMethod || amount == null) {
            const payments = order.payment_ids || [];
            if (!paymentMethod) {
                paymentMethod = payments[0] && payments[0].payment_method_id;
            }
            if (amount == null) {
                amount = payments.reduce((sum, p) => sum + Number(p.amount || 0), 0);
            }
        }

        const printer = await this.ensureFiscalPrinterConnected();
        if (!printer || !printer.isConnected) {
            return {
                valid: false,
                message: _t("Fiscal machine not connected"),
                printer_connection: false,
            };
        }

        // A partir de aquí el puerto queda abierto SOLO durante esta
        // impresión puntual (modelo "bajo demanda"): se libera en el
        // `finally`, pase lo que pase. A diferencia de la caja
        // (`FiscalPrinterButton`), el Kiosko es desatendido y no tiene botón
        // para desconectar manualmente — sin este `finally`, el puerto
        // (Web Serial es exclusivo) quedaba retenido por la pestaña del
        // Kiosko indefinidamente tras la primera impresión, y ningún otro
        // consumidor (otra caja, el backoffice) podía tomarlo hasta reiniciar
        // el navegador. La próxima impresión reconecta sola (autoConnect, sin
        // gesto del usuario, ya que el puerto ya fue autorizado antes).
        try {
            const payload = buildKioskFiscalPayload(order, {
                config: this.config,
                company: this.company,
                currency: this.currency,
                paymentMethodCode: paymentMethod?.code_fiscal_printer,
                paymentAmount: amount,
            });
            if (!payload.valid) {
                return { valid: false, message: payload.message };
            }

            let response;
            try {
                response = await printer.printInvoice(payload);
            } catch (error) {
                console.error("[MF Kiosk] Error printing on the fiscal machine", error);
                return {
                    valid: false,
                    message: String(error?.message || error || _t("Error while printing")),
                    printer_connection: true,
                };
            }

            if (!response || !response.success) {
                return {
                    valid: false,
                    message: (response && response.error) || _t("Error while printing on the fiscal machine"),
                    printer_connection: true,
                };
            }

            // Guardar los datos de la MF en la orden en cliente (espejo de
            // PosStore.set_data_from_fiscal_machine).
            order.fiscal_machine = response.serial || response.serial_machine || "TFHKA-LOCAL";
            order.mf_invoice_number = response.invoiceNumber || response.invoice_number || "";
            order.mf_reportz = String(response.reportZ || response.mf_reportz || "");

            // Persistir el número en el servidor (orden + account.move) vía
            // write_mf_invoice_data, igual que la caja (PrintPendingOrderButton).
            // Solo si la orden YA está registrada en Odoo (id numérico). Con el
            // modelo "registrar-primero" siempre lo estará al llegar aquí.
            const persisted = await this._persistKioskFiscalNumber(order);
            return { valid: true, message: "", response, persisted };
        } finally {
            await this._releaseFiscalPrinterConnection(printer);
        }
    },

    /**
     * Libera (cierra) el puerto serial de la máquina fiscal tras una
     * impresión/reimpresión puntual del Kiosko. Espeja `FiscalPrinterButton.
     * _disconnect` de `l10n_ve_pos_mf`, pero automático: el Kiosko no tiene
     * cajero que pueda pulsar "desconectar", así que cada operación debe
     * soltar el puerto ella misma al terminar (haya salido bien o mal).
     */
    async _releaseFiscalPrinterConnection(printer) {
        const target = printer || this.getFiscalPrinter();
        if (!target || !target.isConnected) {
            return;
        }
        try {
            await target.disconnect();
        } catch (error) {
            console.error("[MF Kiosk] Error al liberar el puerto tras la operación", error);
        }
    },

    /**
     * Persiste `mf_invoice_number`/`fiscal_machine`/`mf_reportz` en el servidor
     * (orden + account.move) vía el endpoint público del Kiosko, que delega en
     * `pos.order.write_mf_invoice_data`. Devuelve true si persistió.
     *
     * Si la orden aún no está sincronizada (id no numérico) no hay nada que
     * persistir por RPC (el número viajará con la orden al registrarse). Si el
     * RPC falla, el papel YA salió y la orden YA existe en Odoo: se guarda el
     * número en un almacén DURABLE (localStorage) como "impreso pendiente de
     * persistir", para reintentar el `write` más tarde (al recargar, o desde el
     * panel) SIN reimprimir. Esto evita que, tras un reload, la orden se vea
     * "sin imprimir" y `printOrReprintKioskOrder` emita un documento fiscal
     * NUEVO (doble emisión).
     */
    async _persistKioskFiscalNumber(order) {
        if (typeof order.id !== "number") {
            return false;
        }
        try {
            const res = await rpc(
                "/l10n_ve_pos_mf_self_order/kiosk/write_mf_invoice_data",
                {
                    access_token: this.access_token,
                    order_id: order.id,
                    mf_invoice_number: order.mf_invoice_number,
                    fiscal_machine: order.fiscal_machine,
                    mf_reportz: order.mf_reportz || false,
                }
            );
            if (!res || !res.success) {
                console.error("[MF Kiosk] write_mf_invoice_data no persistió:", res && res.error);
                this._addPendingFiscalPersist(order);
                return false;
            }
            // Persistió (o el server confirmó un reintento idempotente del mismo
            // número): limpiar cualquier marca pendiente de esta orden.
            this._removePendingFiscalPersist(order.id);
            return true;
        } catch (error) {
            console.error("[MF Kiosk] falló persistir el número fiscal en el servidor", error);
            this._addPendingFiscalPersist(order);
            return false;
        }
    },

    // --- Persistencias de número fiscal pendientes (durables) --------------
    // Mapa en localStorage { [order_id]: {mf_invoice_number, fiscal_machine,
    // mf_reportz} } de órdenes cuyo papel fiscal SÍ salió pero cuyo
    // `write_mf_invoice_data` falló. Sobrevive a un reload para reintentar el
    // write (no la impresión) y para no re-emitir un documento nuevo.

    _PENDING_FISCAL_KEY: "l10n_ve_pos_mf_self_order.pending_fiscal_persist",

    _readPendingFiscalPersists() {
        try {
            const raw = window.localStorage.getItem(this._PENDING_FISCAL_KEY);
            return raw ? JSON.parse(raw) : {};
        } catch (error) {
            console.error("[MF Kiosk] no se pudo leer persistencias fiscales pendientes", error);
            return {};
        }
    },

    _writePendingFiscalPersists(map) {
        try {
            window.localStorage.setItem(this._PENDING_FISCAL_KEY, JSON.stringify(map));
        } catch (error) {
            console.error("[MF Kiosk] no se pudo guardar persistencias fiscales pendientes", error);
        }
    },

    _addPendingFiscalPersist(order) {
        if (typeof order.id !== "number" || !order.mf_invoice_number) {
            return;
        }
        const map = this._readPendingFiscalPersists();
        map[order.id] = {
            mf_invoice_number: order.mf_invoice_number,
            fiscal_machine: order.fiscal_machine,
            mf_reportz: order.mf_reportz || false,
        };
        this._writePendingFiscalPersists(map);
    },

    _removePendingFiscalPersist(orderId) {
        const map = this._readPendingFiscalPersists();
        if (orderId in map) {
            delete map[orderId];
            this._writePendingFiscalPersists(map);
        }
    },

    /**
     * Si la orden quedó "impresa pendiente de persistir", copia su número fiscal
     * (guardado localmente) de vuelta a la orden en memoria. Así
     * `printOrReprintKioskOrder` la ve como YA impresa y NO emite un documento
     * nuevo. No pisa un número ya presente.
     */
    _hydratePendingFiscalNumber(order) {
        if (!order || typeof order.id !== "number" || order.mf_invoice_number) {
            return;
        }
        const pending = this._readPendingFiscalPersists()[order.id];
        if (pending) {
            order.mf_invoice_number = pending.mf_invoice_number;
            order.fiscal_machine = pending.fiscal_machine;
            order.mf_reportz = pending.mf_reportz || "";
        }
    },

    /**
     * Reintenta persistir en el servidor los números fiscales que quedaron
     * pendientes (papel emitido, `write_mf_invoice_data` fallido). Reintenta el
     * WRITE, nunca la impresión. Idempotente en el server: reenviar el mismo
     * número no re-numera (guard de `write_mf_invoice_data`). Fire-and-forget.
     */
    async retryPendingFiscalPersists() {
        const map = this._readPendingFiscalPersists();
        const ids = Object.keys(map);
        if (!ids.length) {
            return;
        }
        for (const orderId of ids) {
            const data = map[orderId];
            if (!data || !data.mf_invoice_number) {
                this._removePendingFiscalPersist(Number(orderId));
                continue;
            }
            try {
                const res = await rpc(
                    "/l10n_ve_pos_mf_self_order/kiosk/write_mf_invoice_data",
                    {
                        access_token: this.access_token,
                        order_id: Number(orderId),
                        mf_invoice_number: data.mf_invoice_number,
                        fiscal_machine: data.fiscal_machine,
                        mf_reportz: data.mf_reportz || false,
                    }
                );
                if (res && res.success) {
                    this._removePendingFiscalPersist(Number(orderId));
                }
            } catch (error) {
                // Sigue pendiente: se reintenta en el próximo arranque/panel.
                console.error(
                    "[MF Kiosk] reintento de persistencia fiscal falló para la orden",
                    orderId,
                    error
                );
            }
        }
    },

    /**
     * Imprime la orden si está pendiente (sin número), o reimprime una COPIA si
     * ya tiene número fiscal. Punto único para el panel de órdenes fiscales.
     *
     * El listado de órdenes gestionables lo aporta el servicio de base
     * (`kioskSessionOrders` en `l10n_ve_pos_self_order/self_order_recovery.js`);
     * aquí solo vive la lógica de impresión/reimpresión.
     */
    async printOrReprintKioskOrder(order) {
        if (!order) {
            return { valid: false, message: _t("Invalid order") };
        }
        // Si la orden quedó "impresa pendiente de persistir" (el papel salió pero
        // `write_mf_invoice_data` falló), recuperar su número local: así se
        // reimprime una COPIA en vez de emitir un documento fiscal NUEVO. El
        // reintento de la persistencia corre aparte (`retryPendingFiscalPersists`).
        this._hydratePendingFiscalNumber(order);
        return order.mf_invoice_number
            ? this.reprintKioskFiscalCopy(order)
            : this.printKioskFiscalInvoice(order);
    },

    /**
     * Reimprime una COPIA de una factura fiscal ya emitida, por su número, vía
     * el comando de reimpresión de la máquina (`TfhkaDriver.reprintDocument`) —
     * el mismo que usa la caja (`ReprintInvoiceButton`). No emite un documento
     * nuevo ni cambia la numeración.
     */
    async reprintKioskFiscalCopy(order) {
        if (!order || !order.mf_invoice_number) {
            return { valid: false, message: _t("The order has no fiscal number; use Print.") };
        }
        const printer = await this.ensureFiscalPrinterConnected();
        if (!printer || !printer.isConnected) {
            return { valid: false, message: _t("Fiscal machine not connected") };
        }
        try {
            const result = await printer.reprintDocument({
                type: "out_invoice",
                number: order.mf_invoice_number,
            });
            if (!result || !result.success) {
                return {
                    valid: false,
                    message: (result && result.error) || _t("Error while reprinting the copy"),
                };
            }
            return { valid: true };
        } catch (error) {
            console.error("[MF Kiosk] error al reimprimir copia", error);
            return { valid: false, message: String((error && error.message) || error) };
        } finally {
            await this._releaseFiscalPrinterConnection(printer);
        }
    },
});
