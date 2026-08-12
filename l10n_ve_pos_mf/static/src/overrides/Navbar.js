/** @odoo-module */

import { Navbar } from "@point_of_sale/app/components/navbar/navbar";
import { patch } from "@web/core/utils/patch";
import { FiscalPrinterButton } from "../components/FiscalPrinterButton/FiscalPrinterButton";

/**
 * Registra el botón de conexión de la máquina fiscal como componente del
 * Navbar del POS (se inyecta en .status-buttons vía herencia del template
 * point_of_sale.Navbar — ver xml/Navbar.xml).
 */
patch(Navbar, {
    components: { ...Navbar.components, FiscalPrinterButton },
});
