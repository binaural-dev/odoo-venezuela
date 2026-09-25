import { patch } from "@web/core/utils/patch";
import { useState, onWillUnmount } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { formatProductName } from "@pos_self_order/app/utils";
import { ProductListPage } from "@pos_self_order/app/pages/product_list_page/product_list_page";

// Max results rendered by the search box at once, so a large catalog does not
// paint thousands of cards on every keystroke. The user narrows by typing more.
const SEARCH_RESULTS_LIMIT = 50;

patch(ProductListPage.prototype, {
    setup() {
        super.setup();
        // Only used when the catalog is hidden (scan / search only mode).
        this.searchState = useState({ query: "" });
        // In scan/search-only mode a barcode scan should keep the customer on
        // this screen (the order builds up in the in-place summary) instead of
        // jumping to the cart. The router honours this flag; see
        // overrides/self_order_router_service.js.
        this.router.suppressScanCartNav = this.hideCatalog;
        onWillUnmount(() => {
            this.router.suppressScanCartNav = false;
        });
    },

    /**
     * Kiosk "scan / search only": the product catalog (categories + grid) is
     * hidden and replaced by a greeting + a search box + the live order
     * summary. Barcode scanning keeps working (wired globally in
     * self_order_service) and now stays on this screen.
     */
    get hideCatalog() {
        const config = this.selfOrder.config;
        return config.self_ordering_mode === "kiosk" && config.self_ordering_hide_catalog;
    },

    get greeting() {
        const partner = this.selfOrder.currentOrder?.partner_id;
        const name = partner?.name;
        return name ? _t("Hi %(name)s!", { name }) : _t("Hi!");
    },

    get searchPlaceholder() {
        return _t("Search or scan a product…");
    },

    get scanHint() {
        return _t("Scan a product or type its name to search.");
    },

    get noResultsHint() {
        return _t("No products match your search.");
    },

    get orderSummaryTitle() {
        return _t("Your order");
    },

    // Products matching the typed query (name / barcode / internal reference).
    // Only self-order-available products, capped for performance.
    get searchResults() {
        const query = this.searchState.query.trim().toLowerCase();
        if (!query) {
            return [];
        }
        const results = [];
        for (const tmpl of this.selfOrder.models["product.template"].getAll()) {
            if (!tmpl.self_order_available) {
                continue;
            }
            const haystack = [tmpl.name, tmpl.display_name, tmpl.barcode, tmpl.default_code]
                .filter(Boolean)
                .join(" ")
                .toLowerCase();
            if (haystack.includes(query)) {
                results.push(tmpl);
                if (results.length >= SEARCH_RESULTS_LIMIT) {
                    break;
                }
            }
        }
        return results;
    },

    // Top-level lines of the current order (combo children are shown nested by
    // their parent, not on their own row).
    get orderLines() {
        return (this.selfOrder.currentOrder?.lines || []).filter(
            (line) => !line.combo_parent_id
        );
    },

    // Show the live summary when the catalog is hidden, the customer is not
    // searching, and the order already has something in it.
    get showOrderSummary() {
        return this.hideCatalog && !this.searchState.query.trim() && this.orderLines.length > 0;
    },

    // The base grid iterates productCategories and renders getProducts(category).
    // In scan/search mode we feed it a single synthetic category driven by the
    // search box, reusing the exact same product cards + tap-to-add behaviour.
    get productCategories() {
        if (this.hideCatalog) {
            return [{ id: "__ve_search_results__", name: "" }];
        }
        return super.productCategories;
    },

    getProducts(category) {
        if (this.hideCatalog) {
            return this.searchResults;
        }
        return super.getProducts(category);
    },

    // --- In-place order summary helpers (mirror the cart page behaviour) ---

    getLinePrice(line) {
        const childLines = line.combo_line_ids;
        if (!childLines || childLines.length === 0) {
            return line.getDisplayPriceWithQty(line.qty);
        }
        let price = 0;
        for (const child of childLines) {
            price += child.getDisplayPriceWithQty(child.qty);
        }
        return price;
    },

    changeLineQuantity(line, increase) {
        for (const cline of line.combo_line_ids || []) {
            this.changeLineQuantity(cline, increase);
        }
        increase ? line.qty++ : line.qty--;
        if (line.qty <= 0) {
            this.selfOrder.removeLine(line);
        }
    },

    removeSummaryLine(line) {
        this.selfOrder.removeLine(line);
    },

    formatProductName(product) {
        return formatProductName(product);
    },

    review() {
        // In scan/search-only mode the in-place summary already replaces the
        // cart page, so paying skips it and goes straight to payment methods.
        if (this.hideCatalog) {
            return this.payDirectly();
        }
        return super.review();
    },

    /**
     * Pay without the intermediate cart page. Mirrors CartPage.pay() but drops
     * the mobile/table-service branches (hideCatalog is kiosk-only). If the
     * customer's required info is somehow incomplete, fall back to the full
     * cart flow so its information popup can collect what's missing.
     */
    async payDirectly() {
        const selfOrder = this.selfOrder;
        if (selfOrder.rpcLoading || !selfOrder.verifyCart()) {
            return;
        }

        const order = selfOrder.currentOrder;
        const partner = order.partner_id || {};
        const time = order.preset_time ? order.preset_time.toSQL() : null;
        const validInfo = selfOrder.isValidSelection(time, {
            id: parseInt(partner.id),
            name: partner.name || order.floating_order_name,
            email: partner.email || order.email,
            phone: partner.phone || order.mobile,
            street: partner.street,
            city: partner.city,
            country_id: partner.country_id,
            state_id: partner.state_id,
            zip: partner.zip,
        });
        if (!validInfo) {
            // Let the full cart flow (with its info popup) handle it.
            this.router._allowScanCartNav = true;
            return super.review();
        }

        selfOrder.rpcLoading = true;
        try {
            await selfOrder.confirmOrder();
        } finally {
            selfOrder.rpcLoading = false;
        }
    },

    // Guard the category-bar helpers: their DOM refs are removed by the
    // template when the catalog is hidden, so skip them entirely.
    ensureCategoryVisible() {
        if (this.hideCatalog) {
            return;
        }
        return super.ensureCategoryVisible();
    },

    toggleSubCategoryPanel() {
        if (this.hideCatalog) {
            return;
        }
        return super.toggleSubCategoryPanel();
    },

    getSubCategories() {
        if (this.hideCatalog) {
            return [];
        }
        return super.getSubCategories();
    },

    selectProduct(product, target) {
        super.selectProduct(product, target);
        // Reset the search after adding a simple product so the next scan/search
        // starts from a clean box (configurable/combo products navigate away).
        if (this.hideCatalog) {
            this.searchState.query = "";
        }
    },
});
