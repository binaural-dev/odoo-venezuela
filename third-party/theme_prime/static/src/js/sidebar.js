/** @odoo-module **/

import "website_sale.cart";
import VariantMixin from "sale.VariantMixin";
import concurrency from "web.concurrency";
import publicWidget from "web.public.widget";
import wSaleUtils from "website_sale.utils";
import Widget from "web.Widget";
import { qweb, _t } from "web.core";

// Disabled cart popover (Odoo Default)
publicWidget.registry.websiteSaleCartLink.include({
    selector: '#top_menu a[href$="/shop/cart"]:not(.tp-cart-sidebar-action)',
});

//------------------------------------------------------------------------------
// Generic
//------------------------------------------------------------------------------
export const Sidebar = Widget.extend({
    template: "theme_prime.Sidebar",
    events: Object.assign({}, Widget.prototype.events, {
        "hidden.bs.offcanvas": "_onHideOffcanvas",
    }),
    init: function (parent, options={}) {
        this._super(parent);
        this._offcanvasInstance = false;
        this.options = options;
        this.lazyLoad = true;
        if ("lazyLoad" in options) {
            this.lazyLoad = options.lazyLoad;
        }
    },
    start: async function () {
        await this._super(...arguments);
        this._appendContent();
    },
    _appendContent: async function () {
        if (this.lazyLoad) {
            this._renderLoader();
            await this._getContent().then(content => {
                this.$loader.remove();
                this.$('.content').replaceWith($(content));
            });
        } else {
            const content = await this._getContent();
            this.$('.content').replaceWith($(content));
        }
    },
    _renderLoader: function () {
        this.$loader = $(qweb.render("theme_prime.Loader", {loadingStr: this.options.loadingStr, height: "100vh"}));
        this.$loader.appendTo(this.$('.content'));
    },
    _getContent: function () {
        if (this.options.contentHtml) {
            return Promise.resolve(this.options.contentHtml);
        }
        return $.get(this.options.fetchUrl || "", this.options.fetchParams || {});
    },
    show: function () {
        return this.appendTo(this.options.parentSelector || "body").then(() => {
            this._offcanvasInstance = new Offcanvas(this.el);
            this._offcanvasInstance.show();
            return this._offcanvasInstance;
        });
    },
    _onHideOffcanvas: function () {
        this.destroy();
    },
});

//------------------------------------------------------------------------------
// Cart Sidebar
//------------------------------------------------------------------------------
export const CartSidebar = Sidebar.extend(VariantMixin, {
    events: Object.assign({}, Sidebar.prototype.events, {
        "click .tp-remove-line": "_onRemoveLine",
        "click .tp-clear-cart": "_onClearCart",
        "click .js_add_cart_json": "onClickAddCartJSON",
        "change .js_quantity": "_onChangeQty",
        "click .show_coupon": "_onClickShowCoupon",
        'click .a-submit': '_onClickApplyCoupon',
    }),
    init: function () {
        this._super.apply(this, arguments);
        this._onChangeQty = _.debounce(this._onChangeQty, 200);
        this.dp = new concurrency.DropPrevious();
    },
    _onClickShowCoupon: function (ev) {
        this.$(".show_coupon").hide();
        this.$(".coupon_form").removeClass("d-none");
    },
    _onClickApplyCoupon: function (ev) {
        ev.preventDefault();
        ev.currentTarget.closest("form").submit();
    },
    _appendContent: async function () {
        await this._super(...arguments);
        this.$('.tp-sidebar-header').remove();
    },
    _onRemoveLine: function (ev) {
        ev.preventDefault();
        $(ev.currentTarget).closest(".tp-product-card").find(".js_quantity").val(0).trigger("change");
    },
    async _onChangeQty (ev) {
        const $target = $(ev.currentTarget);
        const qty = parseInt($target.val());
        let params = { product_id: $target.data("productId"), line_id: $target.data("lineId"), set_qty: qty };
        this.dp.add(this._rpc({ route: "/shop/cart/update_json", params: params })).then(data => {
            this._refreshCart(data);
        });
    },
    _onClearCart: function () {
        this.dp.add(this._rpc({ route: "/shop/cart/clear" })).then(data => {
            this._refreshCart({});
        });
    },
    async _refreshCart (data) {
        data["cart_quantity"] = data.cart_quantity || 0;
        wSaleUtils.updateCartNavBar(data);
        const template = await this._getContent();
        this.$el.empty();
        $(template).appendTo(this.$el);
    },
});

publicWidget.registry.TpCartSidebarBtn = publicWidget.Widget.extend({
    selector: ".tp-cart-sidebar-action",
    read_events: {
        "click": "async _onClick",
    },
    _onClick: function (ev) {
        ev.preventDefault();
        return new CartSidebar(this, {
            title: _t("Your Cart"),
            icon: "dri dri-cart",
            fetchUrl: "/shop/cart",
            fetchParams: { type: "tp_cart_sidebar_request" },
            position: ev.currentTarget.dataset.position || "end",
        }).show();
    },
});

//------------------------------------------------------------------------------
// Search Sidebar
//------------------------------------------------------------------------------
export const SearchSidebar = Sidebar.extend({
    _appendContent: async function () {
        await this._super(...arguments);
        this.trigger_up("widgets_start_request", {
            $target: this.$(".o_searchbar_form"),
        });
        this.$(".o_searchbar_form").removeClass("o_wait_lazy_js");
    },
});

publicWidget.registry.TpSearchSidebarBtn = publicWidget.Widget.extend({
    selector: ".tp-search-sidebar-action",
    read_events: {
        "click": "async _onClick",
    },
    _onClick: function (ev) {
        ev.preventDefault();
        return new SearchSidebar(this, {
            title: _t("Search"),
            icon: "dri dri-search",
            class: "tp-search-sidebar",
            fetchUrl: "/theme_prime/get_search_sidebar",
            position: ev.currentTarget.dataset.position || "end",
        }).show();
    },
});

//------------------------------------------------------------------------------
// Menu Sidebar
//------------------------------------------------------------------------------
publicWidget.registry.TpMenuSidebarBtn = publicWidget.Widget.extend({
    selector: ".tp-menu-sidebar-action",
    read_events: {
        "click": "_onClick",
    },
    _onClick: function (ev) {
        ev.preventDefault();
        const menuSidebarEl = document.querySelector(".tp-menu-sidebar");
        if (menuSidebarEl) {
            menuSidebarEl.removeAttribute("aria-hidden"); // Restore animation
            Offcanvas.getOrCreateInstance(menuSidebarEl).show();
        }
    },
});

//------------------------------------------------------------------------------
// Account Info Sidebar
//------------------------------------------------------------------------------
publicWidget.registry.TpAccountInfoSidebarBtn = publicWidget.Widget.extend({
    selector: ".tp-account-info-sidebar-action",
    read_events: {
        "click": "_onClick",
    },
    _onClick: function (ev) {
        ev.preventDefault();
        const accountInfoSidebarEl = document.querySelector(".tp-account-info-sidebar");
        accountInfoSidebarEl.classList.remove("offcanvas-start", "offcanvas-end");
        accountInfoSidebarEl.classList.add(ev.currentTarget.dataset.position ? `offcanvas-${ev.currentTarget.dataset.position}` : "offcanvas-end");
        accountInfoSidebarEl.removeAttribute("aria-hidden"); // Restore animation
        Offcanvas.getOrCreateInstance(accountInfoSidebarEl).show();
    },
});

//------------------------------------------------------------------------------
// Category Sidebar
//------------------------------------------------------------------------------
export const CategorySidebar = Sidebar.extend({
    events: _.extend({}, Sidebar.prototype.events, {
        "click .tp-category-link": "_onClickCategoryLink",
    }),
    _appendContent: async function () {
        this._renderLoader();
        const data = await this._rpc({ route: "/theme_prime/get_categories_list" });
        this.categories = data.categories;
        this.categoryCount = data.category_count;
        this._renderCategories(data.categories.filter(category => !category.parent_id));
    },
    _onClickCategoryLink: function (ev) {
        if (ev.currentTarget.classList.contains("back")) {
            ev.preventDefault();
            let parentCategoryId = false;
            let parentCategories = this.categories.filter(category => !category.parent_id);
            const parentCategory = this.categories.filter(category => category.id == parseInt(ev.currentTarget.dataset.parentId))[0];
            if (parentCategory) {
                if (parentCategory.parent_id) {
                    parentCategoryId = parentCategory.parent_id[0];
                    const siblingCategories = this.categories.filter(category => category.id == parentCategoryId)[0]["child_id"];
                    parentCategories = this.categories.filter(category => siblingCategories.includes(category.id));
                }
            }
            this._renderCategories(parentCategories, parentCategoryId);
        } else if (ev.currentTarget.dataset.hasChild) {
            ev.preventDefault();
            const parentCategoryId = parseInt(ev.currentTarget.dataset.categoryId);
            const childIds = this.categories.filter(category => category.id == parentCategoryId)[0].child_id;
            const childCategories = this.categories.filter(category => childIds.includes(category.id));
            this._renderCategories(childCategories, parentCategoryId);
        }
    },
    _renderCategories: function (categories, parentId=false) {
        const parentCategory = this.categories.filter(category => category.id == parentId)[0];
        const $categories = $(qweb.render("theme_prime.CategorySidebar", { categories, parentCategory, categoryCount: this.categoryCount, options: this.options, config: odoo.dr_theme_config.json_sidebar_config }));
        this.$el.empty();
        $categories.appendTo(this.$el);
    },
});

publicWidget.registry.TpCategorySidebarBtn = publicWidget.Widget.extend({
    selector: ".tp-category-action",
    read_events: {
        "click": "async _onClick",
    },
    _onClick: function (ev) {
        ev.preventDefault();
        return new CategorySidebar(this, {
            noHeader: true,
            loadingStr: _t("Loading Categories..."),
            position: ev.currentTarget.dataset.position || "end"
        }).show();
    },
});

//------------------------------------------------------------------------------
// Similar Product Sidebar
//------------------------------------------------------------------------------
publicWidget.registry.TpSimilarProductSidebarBtn = publicWidget.Widget.extend({
    selector: ".tp_show_similar_products",
    read_events: {
        "click": "async _onClick",
    },
    _onClick: function (ev) {
        ev.preventDefault();
        return new Sidebar(this, {
            title: _t("Similar Products"),
            icon: "fa fa-clone",
            class: "tp-similar-products-sidebar",
            fetchUrl: "/theme_prime/get_similar_products_sidebar",
            fetchParams: { productID: parseInt(ev.currentTarget.dataset.productTemplateId) },
            position: ev.currentTarget.dataset.position || "end",
        }).show();
    },
});
