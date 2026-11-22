/** @odoo-module **/

import { Navbar } from "@point_of_sale/app/navbar/navbar";
import { CurrencyRateBadge } from "@l10n_ve_rate_systray/currency_rate_badge/currency_rate_badge";

// El recuadro de tasa se inserta en la barra del POS (ver navbar_patch.xml).
Navbar.components = { ...Navbar.components, CurrencyRateBadge };
