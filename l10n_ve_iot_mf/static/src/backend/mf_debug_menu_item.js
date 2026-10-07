/** @odoo-module **/

import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { MfFiscalizadorDialog } from "./mf_fiscalizador_dialog";

/**
 * Item del menú de Developer Tools (icono bug) para abrir el
 * Fiscalizador MF (herramienta técnica Web Serial).
 *
 * El registry "debug" espera factories: ({ env, accessRights }) => item | false
 */
function mfFiscalizadorDebugItem({ env }) {
    return {
        type: "item",
        description: _t("Fiscalizador MF"),
        callback: () => {
            env.services.dialog.add(MfFiscalizadorDialog, {});
        },
        sequence: 320,
    };
}

registry
    .category("debug")
    .category("default")
    .add("l10n_ve_iot_mf_fiscalizador", mfFiscalizadorDebugItem);
