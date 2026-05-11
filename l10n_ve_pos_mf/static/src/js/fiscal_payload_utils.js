/** @odoo-module **/

export const FISCAL_TRIPLET_FIELDS = [
    "fiscal_machine",
    "mf_invoice_number",
    "mf_reportz",
];

export const FISCAL_PRINT_CLASSIFICATION = {
    PRINT_FAILED: "print_failed",
    PRINTED_COMPLETE: "printed_complete",
};

export function hasFiscalValue(value) {
    return value !== false && value !== null && value !== undefined && value !== "";
}

export function getFiscalTripletFromJSON(json = {}) {
    return {
        fiscal_machine: json.fiscal_machine || false,
        mf_invoice_number: json.mf_invoice_number || false,
        mf_reportz: json.mf_reportz || false,
    };
}

export function getMissingFiscalFields(payload = {}) {
    return FISCAL_TRIPLET_FIELDS.filter((field) => !hasFiscalValue(payload[field]));
}

export function hasAnyFiscalField(payload = {}) {
    return FISCAL_TRIPLET_FIELDS.some((field) => hasFiscalValue(payload[field]));
}

export function hasCompleteFiscalTriplet(payload = {}) {
    return getMissingFiscalFields(payload).length === 0;
}

export function classifyFiscalPrintResponse(response = {}) {
    if (!response.valid) {
        return {
            type: FISCAL_PRINT_CLASSIFICATION.PRINT_FAILED,
            message: response.message || "Error al imprimir",
            printer_connection: false,
        };
    }

    if (response.pending_sync) {
        return {
            type: FISCAL_PRINT_CLASSIFICATION.PRINT_FAILED,
            message: response.message || "No se pudo confirmar la tripleta fiscal de la impresión.",
            printer_connection: false,
        };
    }

    return {
        type: FISCAL_PRINT_CLASSIFICATION.PRINTED_COMPLETE,
        message: response.message || "Documento fiscal impreso correctamente.",
        printer_connection: true,
    };
}
