/** @odoo-module **/

import { ProductPricelistReport } from "@product/js/pricelist_report/product_pricelist_report";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { Layout } from "@web/search/layout";
import { user } from "@web/core/user";
import { download } from "@web/core/network/download";
import { useState, onWillStart } from "@odoo/owl";

const PAGE_SIZE = 20;

export class L10nVeSalePriceListReport extends ProductPricelistReport {
    static template = "l10n_ve_sale_price_list.ProductPricelistReport";
    static components = { Layout };

    setup() {
        super.setup();
        this.state = useState({
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
            await this.renderHtml();
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
        this.renderHtml();
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
