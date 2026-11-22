/** @odoo-module **/

import { Component, onWillStart, onMounted, onWillUnmount, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { formatFloat } from "@web/core/utils/numbers";
import { formatDate, deserializeDate } from "@web/core/l10n/dates";
import { _t } from "@web/core/l10n/translation";

// Cada cuánto se vuelve a consultar la tasa (pasa a verde sin recargar al cargarla).
const REFRESH_INTERVAL_MS = 5 * 60 * 1000;

/**
 * Recuadro con la última tasa de la moneda configurada en la compañía (p. ej. Bs por USD).
 * Fondo verde: la tasa es de hoy. Fondo rojo: es de una fecha anterior o no hay tasa.
 * No se pinta si la compañía no lo activó (show_rate_systray).
 *
 * Lo usan el systray del backend y la barra superior del POS.
 */
export class CurrencyRateBadge extends Component {
    static template = "l10n_ve_rate_systray.CurrencyRateBadge";
    static props = {
        // Clases del contenedor (p. ej. "o_nav_entry" en el systray del backend).
        wrapperClass: { type: String, optional: true },
        // Compañía a consultar; por defecto la compañía activa del usuario.
        companyId: { type: Number, optional: true },
        // Si falla la consulta (p. ej. POS sin conexión) se conserva la última tasa.
        keepLastOnError: { type: Boolean, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.state = useState({ data: null });

        onWillStart(() => this.load());
        onMounted(() => {
            this.intervalId = setInterval(() => this.load(), REFRESH_INTERVAL_MS);
        });
        onWillUnmount(() => clearInterval(this.intervalId));
    }

    async load() {
        const context = this.props.companyId
            ? { allowed_company_ids: [this.props.companyId] }
            : {};
        try {
            const data = await this.orm.call("res.currency.rate", "get_systray_rate", [], {
                context,
            });
            this.state.data = data && data.currency ? data : null;
        } catch (error) {
            // Sin tasa visible antes que romper la barra superior.
            console.warn("CurrencyRateBadge:: no se pudo obtener la tasa", error);
            if (!this.props.keepLastOnError) {
                this.state.data = null;
            }
        }
    }

    get hasRate() {
        return Boolean(this.state.data.rate);
    }

    get rateLabel() {
        return formatFloat(this.state.data.rate, { digits: [16, 4] });
    }

    get dateLabel() {
        return formatDate(deserializeDate(this.state.data.date));
    }

    get title() {
        const data = this.state.data;
        if (!this.hasRate) {
            return _t("There is no %(currency)s/%(foreign)s rate loaded", {
                currency: data.currency,
                foreign: data.foreign_currency,
            });
        }
        const base = _t("%(currency)s/%(foreign)s rate of %(date)s", {
            currency: data.currency,
            foreign: data.foreign_currency,
            date: this.dateLabel,
        });
        return data.is_today ? base : `${base} — ${_t("today's rate is not loaded")}`;
    }
}
