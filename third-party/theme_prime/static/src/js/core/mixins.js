odoo.define('theme_prime.mixins', function (require) {
"use strict";

let wUtils = require('website.utils');
let { Markup} = require('web.utils');
let {qweb, _t} = require('web.core');
let ConfirmationDialog = require('theme_prime.cart_confirmation_dialog');
let {updateCartNavBar} = require('website_sale.utils');
const { loadJS } = require('@web/core/assets');
const { CartSidebar } = require('@theme_prime/js/sidebar');


let DroggolUtils = {
    _getDomainWithWebsite: function (domain) {
        return domain.concat(wUtils.websiteDomain(this));
    },
    _getShopConfig: async function () {
        return await this._rpc({ model: 'website', method: 'get_theme_prime_shop_config' });
    },
};

let primeUtilities = {
    /**
     * @private
     * As method name suggest will refector someday
     */
    _primeLoadExtras: async function (extraMethod) {
        var proms = [];
        await Promise.all(this.extraLibs.map(async (lib) => { await loadJS(lib);}));
        return await Promise.all(proms).then(() => { if (extraMethod) { extraMethod() }});
    }
};

let MarkupRecords = {
    _markUpValues: function (fieldNames, records) {
        records.forEach(record => {
            for (const fieldName of fieldNames) {
                if (record[fieldName]) {
                    record[fieldName] = Markup(record[fieldName]);
                }
            }
        });
        return records;
    }
};

let B2bMixin = {
    _isB2bModeEnabled: function () {
        let data = $(document.documentElement).data();
        // visibility saved my a**
        // But we will find a better way in next version this is sh*t
        return data && !data.logged && odoo.dr_theme_config.json_b2b_shop_config && odoo.dr_theme_config.json_b2b_shop_config.dr_enable_b2b;
    },

    _loggedInNotification: function () {
        let buttons = [{ text: _t('Log in'), click: () => { window.location = '/web/login'; } }];
        // Ugly hack
        // Just like géry debongnie I don't like Jquery
        odoo.dr_theme_config.has_sign_up ? buttons.push({ text: _t('Sign Up'), click: () => { window.location = '/web/signup'; } }) : buttons.push({ text: _t('Close'), click: () => { $('.o_notification_manager .tp-login-notification').remove() } });
        this.displayNotification({
            className: 'tp-notification tp-login-notification tp-bg-soft-primary o_animate',
            messageIsHtml: true,
            message: Markup(qweb.render('DroggolNotification', { productName: _t('Log in to place an order'), iconClass: 'fa fa-sign-in', color: 'primary', message: _t('Please log in first.') })),
            buttons: buttons,
        });
    },
}

let cartMixin = _.extend({}, B2bMixin, {
    /**
    * @private
    */
    _addProductToCart: function (cartInfo, QuickViewDialog) {
        // Do not add variant for default flow
        let dialogOptions = {mini: true, size: 'small'};
        dialogOptions['variantID'] = cartInfo.productID;
        this.QuickViewDialog = new QuickViewDialog(this, dialogOptions).open();
        var params = {product_id: cartInfo.productID, add_qty: 1};
        if (this._customCartSubmit) {
            this.QuickViewDialog.on('tp_auto_add_product', null, this._customCartSubmit.bind(this, params));
        }
        return this.QuickViewDialog;
    },

    /**
    * @private
    */
    _getCartParams: function (ev) {
        return {productID: parseInt($(ev.currentTarget).attr('data-product-product-id')), qty: 1};
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * @private
     * @param  {Event} ev
     */
    onAddToCartClick: function (ev, QuickViewDialog) {
        if (this._isB2bModeEnabled()) {
            this._loggedInNotification();
        } else {
            this._addProductToCart(this._getCartParams(ev), QuickViewDialog);
        }
    },
});

let ProductCarouselMixins = {
    _bindEvents: function ($target) {
        // Resolve conflict when multiple product carousel on same page
        const $carousel = $target.find('#o-carousel-product');
        $carousel.addClass('d_shop_product_details_carousel');
        $carousel.find('.carousel-indicators li').on('click', ev => {
            ev.stopPropagation();
            $carousel.carousel($(ev.currentTarget).index());
        });
        $carousel.find('.carousel-control-next').on('click', ev => {
            ev.preventDefault();
            ev.stopPropagation();
            $carousel.carousel('next');
        });
        $carousel.find('.carousel-control-prev').on('click', ev => {
            ev.preventDefault();
            ev.stopPropagation();
            $carousel.carousel('prev');
        });
    },
};

let OwlMixin = {
    extraLibs: ['/theme_prime/static/lib/OwlCarousel2-2.3.4/owl.carousel.js'],
    initializeOwlSlider: function (ppr, isTwoColLayout) {
        let responsive = {0: {items: 1}, 576: {items: 2}, 768: {items: 3}, 992: {items: 3}, 1200: {items: ppr}};
        if (this.uiConfigInfo_init && this.uiConfigInfo_init.mobileConfig &&this.uiConfigInfo_init.mobileConfig.style !== 'default') {
            responsive[0] = { items: 2 };
        }
        if (isTwoColLayout) {
            responsive = {0: {items: 1}, 576: {items: ppr}};
        }
        this.$('.droggol_product_slider').owlCarousel({dots: false, margin: 20, stagePadding: 5, rewind: true, rtl: _t.database.parameters.direction === 'rtl', nav: true, navText: ['<i class="dri dri-arrow-left-l"></i>', '<i class="dri dri-arrow-right-l"></i>'], responsive: responsive});
    }
};

let ProductsBlockMixins = {
    _setCamelizeAttrs: function () {
        this._super.apply(this, arguments);
        this.selectionType = false;
        if (this.selectionInfo) {
            this.selectionType = this.selectionInfo.selectionType;
        }
    },
    /**
    * @private
    */
    _getDomain: function () {
        let domain = false;
        switch (this.selectionType) {
            case 'manual':
                if (this.selectionInfo.recordsIDs) {
                    domain = [['id', 'in', this.selectionInfo.recordsIDs]];
                }
                break;
            case 'advance':
                if (_.isArray(this.selectionInfo.domain_params.domain)) {
                    domain = this.selectionInfo.domain_params.domain;
                }
                break;
        }
        return domain ? domain : this._super.apply(this, arguments);
    },
    /**
    * @private
    */
    _getLimit: function () {
        return (this.selectionType === 'advance' ? this.selectionInfo.domain_params.limit || 5 : this._super.apply(this, arguments));
    },
    /**
    * @private
    */
    _getSortBy: function () {
        return (this.selectionType === 'advance' ? this.selectionInfo.domain_params.order : this._super.apply(this, arguments));
    },
    /**
    * @private
    */
    _getProducts: function (data) {
        let {products} = data;
        let selectionInfo = this.selectionInfo;
        if (selectionInfo && selectionInfo.selectionType === 'manual') {
            products = _.map(selectionInfo.recordsIDs, function (productID) {
                return _.findWhere(data.products, {id: productID}) || false;
            });
        }
        return _.compact(products);
    },
    /**
    * @private
    */
    _processData: function (data) {
        this._super.apply(this, arguments);
        return this._getProducts(data);
    },
};

let HotspotMixns = {
    _getHotspotConfig: function () {
        if (this.$target.get(0).dataset.hotspotType === 'static') {
            return {titleText: this.$target.get(0).dataset.titleText, subtitleText: this.$target.get(0).dataset.subtitleText, buttonLink: this.$target.get(0).dataset.buttonLink, hotspotType: this.$target.get(0).dataset.hotspotType, buttonText: this.$target.get(0).dataset.buttonText, imageSrc: this.$target.get(0).dataset.imageSrc};
        }
        return {};
    },
    _isPublicUser: function () {
        return _.has(odoo.dr_theme_config, "is_public_user") && odoo.dr_theme_config.is_public_user;
    },

    _cleanNodeAttr: function () {
        if (this._isPublicUser()) {
            let attrs = ['data-image-src', 'data-hotspot-type', 'data-title-text', 'data-subtitle-text', 'data-button-link', 'data-button-text', 'data-top', 'data-on-hotspot-click'];
            attrs.forEach(attr => {this.$target.removeAttr(attr)});
        }
    },
};

let CategoryPublicWidgetMixins = {

    _setCamelizeAttrs: function () {
        this._super.apply(this, arguments);
        if (this.selectionInfo) {
            var categoryIDs = this.selectionInfo.recordsIDs;
            // first category
            this.initialCategory = categoryIDs.length ? categoryIDs[0] : false;
        }
    },
    /**
     * @private
     * @returns {Array} options
     */
    _getOptions: function () {
        var options = this._super.apply(this, arguments) || {};
        if (!this.initialCategory) {
            return false;
        }
        var categoryIDs = this.selectionInfo.recordsIDs;
        options['order'] = this.uiConfigInfo.sortBy;
        options['limit'] = this.uiConfigInfo.limit;
        // category name id vadi dict first time filter render karva mate
        if (!this.isBrand) {
            options['get_categories'] = true;
        } else {
            options['get_brands'] = true;
        }
        options['categoryIDs'] = categoryIDs;
        options['categoryID'] = this.initialCategory;
        return options;
    },
    /**
     * @private
     * @returns {Array} domain
     */
    _getDomain: function () {
        if (!this.initialCategory) {
            return false;
        }
        var operator = '=';
        if (this.uiConfigInfo.includesChild) {
            operator = 'child_of';
        }
        let domain = [['public_categ_ids', operator, this.initialCategory]]
        if (this.isBrand) {
            domain = [['attribute_line_ids.value_ids', 'in', [this.initialCategory]]];
        }
        return domain;
    },
};

var TabsMixin = {
    bodyTemplate: 'd_s_category_cards_wrapper',
    fieldstoFetch: ['name', 'description_sale', 'dr_label_id', 'rating', 'public_categ_ids', 'product_template_image_ids', 'product_variant_ids', 'dr_stock_label', 'colors'],
    noDataTemplateSubString: _t("Sorry, We couldn't find any products under this category"),

    _getDomainValues: function (recordID) {
        return {};
    },
    /**
     * Activate clicked category
     * @param {Integer} recordID
     * @private
     */
    _activateTab: function (recordID) {
        this.$('.d_s_category_cards_item').addClass('d-none');
        this.$('.d_s_category_cards_item[data-category-id=' + recordID + ']').removeClass('d-none');
    },
    /**
     * Fetch and render products for category
     * @private
     * @param {Integer} recordID
     */
    _fetchAndAppendByCategory: function (recordID) {
        this._activateTab(recordID);
        this._fetchProductsByDomain(this._getDomainValues(recordID)).then(data => {
            this._renderNewProducts(data.products, recordID);
        });
    },
    /**
    * @private
    * @returns {Integer} recordID
    */
    _fetchProductsByDomain: function (params) {
        return this._rpc({route: this.controllerRoute, params: params});
    },
    /**
     * Render and append new products.
     * @private
     * @param {Array} products
     * @param {Integer} recordID
     */
    _renderNewProducts: function (products, recordID) {
        this._markUpValues(this.tpFieldsToMarkUp, products);
        var $tmpl = $(qweb.render('d_s_category_cards_item', {data: products, widget: this, recordID: recordID}));
        this.$('.d_loader_default').remove();
        $tmpl.appendTo(this.$('.d_s_category_cards_container'));
        this.initializeOwlSlider(this.uiConfigInfo.ppr);
        this._reloadWidget({ selector: '.tp_show_similar_products'})
        this._reloadWidget({ selector: '.tp-product-preview-swatches'})
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * @private
     * @param {Event} ev
     */
    _onCategoryTabClick: function (ev) {
        var $target = $(ev.currentTarget);
        this.$('.d_category_lable').removeClass('d_active');
        $target.addClass('d_active');
        var recordID = parseInt($target.attr('data-category-id'), 10);
        if (!this.$('.d_s_category_cards_item[data-category-id=' + recordID + ']').length) {
            if (this.loaderTemplate) {
                var $template = $(qweb.render(this.loaderTemplate));
                $template.addClass('d_loader_default').appendTo(this.$('.d_s_category_cards_container'));
            }
            this._fetchAndAppendByCategory(recordID);
        } else {
            this._activateTab(recordID);
        }
    },
};
var CartManagerMixin = _.extend({}, B2bMixin, {

    _handleCartConfirmation: function (cartFlow, data) {
        cartFlow = cartFlow == 'default'? 'notification' : cartFlow;
        var methodName = _.str.sprintf('_cart%s', _.str.classify(cartFlow));
        return this[methodName](data);
    },

    _cartNotification: function (data) {
        this.displayNotification({
            className: 'tp-notification tp-bg-soft-primary o_animate',
            messageIsHtml: true,
            message: Markup(qweb.render('DroggolNotification', { color: 'primary', productID: data.product_id, productName: data.product_name, message: _t('Added to your cart.')})),
            buttons: [{text: _t('View cart'), click: () => {window.location = '/shop/cart';}}, {text: _t('Checkout'), click: () => {window.location = '/shop/checkout?express=1';}}],
        });
    },

    _cartDialog: function (data) {
        new ConfirmationDialog(this, {data: data, size: 'medium'}).open();
    },

    _cartSideCart: function (data) {
        return new CartSidebar(this, {
            title: _t("Your Cart"),
            icon: "dri dri-cart",
            fetchUrl: "/shop/cart",
            fetchParams: { type: "tp_cart_sidebar_request" },
            position: "end",
        }).show();
    },

    _customCartSubmit: function (params) {
        params.force_create = true;
        params.dr_cart_flow = odoo.dr_theme_config.cart_flow || 'notification';
        return this._rpc({route: "/shop/cart/update_json", params: params}).then(async data => {
            updateCartNavBar(data);
            this.$el.trigger('dr_close_dialog', {});
            return this._handleCartConfirmation(params.dr_cart_flow, data);
        });
    },
});

return {
    DroggolUtils: DroggolUtils,
    HotspotMixns: HotspotMixns,
    ProductCarouselMixins: ProductCarouselMixins,
    CategoryPublicWidgetMixins: CategoryPublicWidgetMixins,
    OwlMixin: OwlMixin,
    ProductsBlockMixins: ProductsBlockMixins,
    CartManagerMixin: CartManagerMixin,
    cartMixin: cartMixin,
    MarkupRecords: MarkupRecords,
    TabsMixin: TabsMixin,
    primeUtilities: primeUtilities,
    B2bMixin: B2bMixin,
};
});
