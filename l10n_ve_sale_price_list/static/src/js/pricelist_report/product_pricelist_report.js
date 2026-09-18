/** @odoo-module **/

import { ProductPricelistReport } from "@product/js/pricelist_report/product_pricelist_report";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { Layout } from "@web/search/layout";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { user } from "@web/core/user";
import { download } from "@web/core/network/download";
import { onWillStart } from "@odoo/owl";

const PAGE_SIZE = 20;
// Threshold from the task: combining a large product selection with many
// pricelists is what made the report slow before pagination/batching
// existed. The on-screen view and the batched price computation
// (_set_pricelist_prices) already keep this from timing out, but the
// PDF/XLSX exports never paginate - large exports still take noticeably
// longer, so the user gets a heads-up instead of no warning at all.
const LARGE_SELECTION_PRODUCT_THRESHOLD = 800;
const LARGE_SELECTION_PRICELIST_THRESHOLD = 5;

export class L10nVeSalePriceListReport extends ProductPricelistReport {
    static template = "l10n_ve_sale_price_list.ProductPricelistReport";
    static components = { Layout, Dropdown, DropdownItem };

    setup() {
        super.setup();
        // Extend the base component's own useState() object instead of
        // replacing it - this.state already carries pricelists/html/etc,
        // and the base class's onWillStart (registered by super.setup(),
        // so it runs before ours) writes into it and calls renderHtml() on
        // its own. Reassigning this.state here used to throw that away.
        Object.assign(this.state, {
            selectedPricelists: [],
            page: 1,
        });

        onWillStart(async () => {
            // Preselect the pricelists that belong to the company the user
            // is currently logged into, plus the ones with no company
            // (shared across all companies). If the active company is a
            // parent, only its own pricelists are matched here — not its
            // children's — since this is a plain equality check, not a
            // hierarchy lookup.
            const companyId = user.activeCompany?.id;
            const domain = companyId
                ? ["|", ["company_id", "=", companyId], ["company_id", "=", false]]
                : [["company_id", "=", false]];
            this.state.selectedPricelists = await this.orm.searchRead(
                "product.pricelist",
                domain,
                ["id", "display_name"]
            );
            // No need to call this.renderHtml() here - the base class's own
            // onWillStart (it runs first, since it was registered first in
            // super.setup()) already renders once after populating
            // state.pricelists, and selectedPricelists above is set before
            // that render resolves.
        });
    }

    // The catalog used to populate the "add a pricelist" dropdown; include
    // the company name (via display_name) so it's clear which company each
    // pricelist belongs to before adding it.
    getPricelists() {
        return this.orm.searchRead("product.pricelist", [], ["id", "display_name"]);
    }

    get totalPages() {
        return Math.max(1, Math.ceil((this.activeIds || []).length / PAGE_SIZE));
    }

    onClickPrevPage() {
        if (this.state.page <= 1) {
            return;
        }
        this.state.page -= 1;
        this.renderHtml();
    }

    onClickNextPage() {
        if (this.state.page >= this.totalPages) {
            return;
        }
        this.state.page += 1;
        this.renderHtml();
    }

    async onClickAddPricelist(ev) {
        ev.preventDefault();
        const selectEl = document.getElementById("pricelists");
        const selectedId = parseInt(selectEl.value);

        const selectedPl = this.state.pricelists.find((pl) => pl.id === selectedId);

        if (!selectedPl) {
            await this.action.doAction({
                type: "ir.actions.client",
                tag: "display_notification",
                params: { type: "danger", message: _t("Selected pricelist not found.") },
            });
            return;
        }

        if (this.state.selectedPricelists.some((pl) => pl.id === selectedId)) {
            await this.action.doAction({
                type: "ir.actions.client",
                tag: "display_notification",
                params: { type: "warning", message: _t("This pricelist is already added.") },
            });
            return;
        }

        this.state.selectedPricelists.push(selectedPl);
        await this._warnIfLargeSelection();
        this.renderHtml();
    }

    // Non-blocking heads-up (not a hard limit): the report still works past
    // this threshold - pagination and the batched price computation already
    // keep the on-screen view responsive - but a combination this large
    // makes the (unpaginated) PDF/XLSX export noticeably slower, so the
    // user gets a chance to reconsider before printing/exporting.
    async _warnIfLargeSelection() {
        const productCount = (this.activeIds || []).length;
        const pricelistCount = this.state.selectedPricelists.length;
        if (
            productCount > LARGE_SELECTION_PRODUCT_THRESHOLD &&
            pricelistCount >= LARGE_SELECTION_PRICELIST_THRESHOLD
        ) {
            await this.action.doAction({
                type: "ir.actions.client",
                tag: "display_notification",
                params: {
                    type: "warning",
                    message: _t(
                        "You selected %(products)s products and %(pricelists)s pricelists. Printing or exporting such a large combination may take a while.",
                        { products: productCount, pricelists: pricelistCount }
                    ),
                },
            });
        }
    }

    async onClickRemovePricelist(ev) {
        const id = parseInt(ev.target.closest("span").dataset.id);
        this.state.selectedPricelists = this.state.selectedPricelists.filter((pl) => pl.id !== id);
        this.renderHtml();
    }

    // Params used for the on-screen HTML preview: scoped to the current page
    // so the server only has to compute prices for PAGE_SIZE products.
    get reportParams() {
        return {
            active_model: this.activeModel || "product.template",
            active_ids: this.activeIds || [],
            display_pricelist_title: this.displayPricelistTitle || "",
            pricelist_ids: this.state.selectedPricelists.map((pl) => pl.id) || "",
            quantities: this.quantities || [1],
            page: this.state.page,
            page_size: PAGE_SIZE,
        };
    }

    // Params used for PDF export: the printed report must always cover every
    // selected product regardless of which page is currently on screen, so
    // pagination is intentionally left out here.
    get printParams() {
        const { page, page_size, ...rest } = this.reportParams;
        return rest;
    }

    async onClickPrint() {
        await this._warnIfLargeSelection();
        this.export_pdf();
    }

    export_pdf() {
        this.action.doAction({
            type: "ir.actions.report",
            report_type: "qweb-pdf",
            report_name: "product.report_pricelist",
            report_file: "product.report_pricelist",
            data: this.printParams,
        });
    }

    // Excel export always covers every selected product, same as the PDF —
    // it reuses printParams (no page/page_size) rather than reportParams.
    async onClickExportExcel() {
        if (!this.state.selectedPricelists.length) {
            await this.action.doAction({
                type: "ir.actions.client",
                tag: "display_notification",
                params: { type: "warning", message: _t("Select at least one pricelist first.") },
            });
            return;
        }
        await this._warnIfLargeSelection();
        try {
            await download({
                url: "/product/export/pricelist/",
                data: {
                    report_data: JSON.stringify(this.printParams),
                    export_format: "xlsx",
                },
            });
        } catch (error) {
            console.error("Error exporting XLSX file:", error);
            await this.action.doAction({
                type: "ir.actions.client",
                tag: "display_notification",
                params: { type: "danger", message: _t("Error exporting file. Please try again.") },
            });
        }
    }
}

registry.category("actions").remove("generate_pricelist_report");
registry.category("actions").add("generate_pricelist_report", L10nVeSalePriceListReport);
