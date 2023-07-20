odoo.define('theme_prime.dynamic_snippets', function (require) {
"use strict";

const {_t, qweb} = require('web.core');
const publicWidget = require('web.public.widget');
const ProductRootWidget = require('theme_prime.product.root.widget');
const RootWidget = require('theme_prime.root.widget');
const config = require('web.config');
const QuickViewDialog = require('theme_prime.product_quick_view');
const sAnimations = require('website.content.snippets.animation');
const { OwlMixin, MarkupRecords, ProductsBlockMixins, CategoryPublicWidgetMixins, ProductCarouselMixins, CartManagerMixin, HotspotMixns, cartMixin, TabsMixin} = require('theme_prime.mixins');
require('website.content.menu');

// Hack ODOO is handling hover by self so manually trigger event remove when new bootstrap is merged in ODOO :)

publicWidget.registry.hoverableDropdown.include({
    _onMouseEnter: function (ev) {
        if (config.device.size_class <= config.device.SIZES.SM) {return}
        // currentTarget dropdown
        $(ev.currentTarget).trigger('show.tp.dropdown');
        this._super.apply(this, arguments);
    },
});

publicWidget.registry.tp_preview_wrapper = publicWidget.Widget.extend({
    selector: '#tp_wrap',
    events: {
        'click': '_onClick',
        'tp-reload': '_onReload',
    },
    start: function () {
        window.dispatchEvent(new CustomEvent('TP_WRAPPER_READY'));
        $('body').addClass('tp-preview-element');
        $('.tp-bottombar-component .tp-bottom-action-btn').addClass('pe-none');
        return this._super.apply(this, arguments);
    },
    _onClick: function (ev) {
        ev.preventDefault();
        ev.stopPropagation();
    },
    _onReload: function () {
        this.$domEl = this.$('.tp-droggol-dynamic-snippet');
        this._setOffsetPosition();
        this.trigger_up('widgets_start_request', {editableMode: true, $target: this.$domEl});
    },
    _setOffsetPosition: function () {
        this.$domEl.find('> .container').removeClass('container').addClass('container-fluid');
    }
});

// Products Cards
publicWidget.registry.s_d_products_snippet = ProductRootWidget.extend(OwlMixin, ProductsBlockMixins, {
    selector: '.s_d_products_snippet_wrapper',

    bodyTemplate: 'd_s_cards_wrapper',
    bodySelector: '.s_d_products_snippet',
    controllerRoute: '/theme_prime/get_products_data',
    fieldstoFetch: ['name', 'dr_label_id', 'rating', 'public_categ_ids', 'product_variant_ids', 'dr_stock_label', 'colors'],
    snippetNodeAttrs: (ProductRootWidget.prototype.snippetNodeAttrs || []).concat(['data-selection-info']),

    /**
     * initialize owlCarousel.
     * @private
     */
    _modifyElementsAfterAppend: function () {
        this._super.apply(this, arguments);
        if (this.uiConfigInfo.mode === 'slider') {
            this.initializeOwlSlider(this.uiConfigInfo.ppr);
        }
    },
});

publicWidget.registry.s_product_listing_cards_wrapper = ProductRootWidget.extend(ProductsBlockMixins, MarkupRecords, {
    selector: '.s_product_listing_cards_wrapper',
    bodyTemplate: 'd_s_cards_listing_wrapper',
    bodySelector: '.s_product_listing_cards',
    controllerRoute: '/theme_prime/get_listing_products',
    fieldstoFetch: ['name', 'rating'],
    snippetNodeAttrs: (ProductRootWidget.prototype.snippetNodeAttrs || []).concat(['data-selection-info', 'data-ui-config-info']),

    _getOptions: function () {
        let value = _.pick(this.uiConfigInfo || {}, function (value, key, object) {
            return _.contains(['bestseller', 'newArrived', 'discount'], key) && value;
        });
        value['mode'] = this.selectionInfo.selectionType || 'manual';
        value['shop_config_params'] = true;
        return value;
    },
    _processData: function (data) {
        this.numOfCol = 12 / _.keys(data.products).length;
        let result = [];
        _.each(data.products, (list, key) => {
            switch (key) {
                case 'bestseller':
                    result.push({title: _t("Best Seller"), products: list});
                    break;
                case 'newArrived':
                    result.push({title: _t("Newly Arrived"), products: list});
                    break;
                case 'discount':
                    result.push({title: _t("On Sale"), products: list});
                    break;
            }
            this._markUpValues(this.tpFieldsToMarkUp, list);
        });
        return result;
    },
    _getLimit: function () {
        return this.uiConfigInfo.limit || 5;
    }
});

// Countdown snippet
publicWidget.registry.s_d_single_product_count_down = ProductRootWidget.extend(ProductsBlockMixins, {
    selector: '.s_d_single_product_count_down_wrapper',

    bodyTemplate: 's_d_single_product_count_down_temp',
    bodySelector: '.s_d_single_product_count_down',

    controllerRoute: '/theme_prime/get_products_data',

    snippetNodeAttrs: (ProductRootWidget.prototype.snippetNodeAttrs || []).concat(['data-selection-info']),

    fieldstoFetch: ['name', 'offer_data', 'description_sale'],

    extraLibs: (ProductRootWidget.prototype.extraLibs || []).concat(['/theme_prime/static/lib/OwlCarousel2-2.3.4/owl.carousel.js']),
    /**
     * initialize owlCarousel.
     * @private
     */
    _modifyElementsAfterAppend: function () {
        this._super.apply(this, arguments);
        this._reloadWidget({ selector: '.tp-countdown'});
        this.$('.droggol_product_slider_single_product').owlCarousel({ dots: false, margin: 20, rtl: _t.database.parameters.direction === 'rtl', stagePadding: 5, rewind: true, nav: true, navText: ['<i class="dri dri-arrow-left-l"></i>', '<i class="dri dri-arrow-right-l"></i>'], responsive: {0: {items: 1,},}});
    },
});

publicWidget.registry.s_product_listing_tabs_snippet = ProductRootWidget.extend(OwlMixin, MarkupRecords, TabsMixin, {
    selector: '.s_product_listing_tabs_wrapper',
    controllerRoute: '/theme_prime/get_tab_listing_products',
    bodySelector: '.s_product_listing_tabs',
    supportedTypes: ['bestseller', 'discount', 'newArrived'],
    snippetNodeAttrs: (ProductRootWidget.prototype.snippetNodeAttrs || []).concat(['data-selection-info']),
    read_events: _.extend({ 'click .d_category_lable': '_onCategoryTabClick' }, ProductRootWidget.prototype.read_events),

    _getDomainValues: function (recordID) {
        let { limit } = this.uiConfigInfo;
        let params = { limit: limit, fields: this.fieldstoFetch };
        let selectedTab = _.findWhere(this.categories, {id: recordID});
        let productListingType = selectedTab ? selectedTab.type : 'bestseller';
        if (productListingType === 'discount') {
            params['domain'] = [['dr_has_discount', '!=', false]];
        } else {
            params['order'] = this._getSortbyValue(productListingType);
        }
        if (this.domainRecordID) {
            params['options'] = { categoryID: this.domainRecordID };
        }
        return params;
    },
    _getSortbyValue: function (productListingType) {
        if (productListingType === 'bestseller') {
            return productListingType;
        }
        if (productListingType === "newArrived") {
            return 'create_date desc';
        }
        return false;
    },
    _getOptions: function () {
        if (this.selectionInfo && this.selectionInfo.recordsIDs && this.selectionInfo.recordsIDs.length) {
            this.domainRecordID = this.selectionInfo.recordsIDs[0];
            return { categoryID: this.domainRecordID, shop_config_params: true};
        }
        return {shop_config_params: true};
    },
    _setCamelizeAttrs: function () {
        this._super.apply(this, arguments);
        this.initialType = false;
        this.categories = [];
        let labels = {bestseller:  _t("Best Sellers"), discount: _t("On Sale"), newArrived:  _t("Newly Arrived")};
        this.supportedTypes.forEach((type, index) => {
            this.initialType = !this.initialType && this.uiConfigInfo[type] ? type : this.initialType;
            if (this.uiConfigInfo[type]) {
                this.categories.push({id: index+1, name: labels[type], type:type});
            }
        });
    },
    /**
     * initialize owlCarousel.
     * @override
     */
    _modifyElementsAfterAppend: function () {
        this._super.apply(this, arguments);
        if (this.uiConfigInfo.mode === 'slider') {
            this.initializeOwlSlider(this.uiConfigInfo.ppr);
        }
    },
    _getSortBy: function () {
        return this._getSortbyValue(this.initialType);
    },
    _getLimit: function () {
        return this.uiConfigInfo.limit || 5;
    },
    _getDomain: function () {
        return this.initialType === 'discount' ? [['dr_has_discount', '!=', false]] : false;
    },
    _processData: function (data) {
        this._markUpValues(this.tpFieldsToMarkUp, data.products);
        if (data.listing_category && data.listing_category.length) {
            this.listing_category = data.listing_category[0];
        }
        this._super.apply(this, arguments);
        return data.products;
    },
});

publicWidget.registry.s_category_snippet = ProductRootWidget.extend(OwlMixin, MarkupRecords, CategoryPublicWidgetMixins, TabsMixin, {
    selector: '.s_d_category_snippet_wrapper, .s_products_by_brands_tabs_wrapper',
    bodySelector: '.s_d_category_snippet',
    snippetNodeAttrs: (ProductRootWidget.prototype.snippetNodeAttrs || []).concat(['data-selection-info']),
    controllerRoute: '/theme_prime/get_products_by_category',
    read_events: _.extend({'click .d_category_lable': '_onCategoryTabClick'}, ProductRootWidget.prototype.read_events),

    start: function () {
        this.isBrand = this.$target.hasClass('s_products_by_brands_tabs_wrapper');
        if (this.isBrand) {
            this.bodySelector = '.s_products_by_brands_tabs';
        }
        return this._super.apply(this, arguments);
    },
    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    _getDomainValues: function (categoryID) {
        let { includesChild, sortBy, limit } = this.uiConfigInfo;
        var operator = '=';
        if (includesChild) {
            operator = 'child_of';
        }
        let domain = [['public_categ_ids', operator, categoryID]]
        if (this.isBrand) {
            domain = [['attribute_line_ids.value_ids', 'in', [categoryID]]];
        }
        return { domain: domain, options:{order: sortBy,limit: limit} ,fields: this.fieldstoFetch};
    },
    /**
     * initialize owlCarousel.
     * @override
     */
    _modifyElementsAfterAppend: function () {
        this._super.apply(this, arguments);
        var categories = this.fetchedCategories;
        // if first categories is archive or moved to another website then activate first category
        if (categories.length && categories[0] !== this.initialCategory) {
            this._fetchAndAppendByCategory(categories[0]);
        }
        if (this.uiConfigInfo.mode === 'slider') {
            this.initializeOwlSlider(this.uiConfigInfo.ppr);
        }
    },
    /**
     * @override
     */
    _processData: function (data) {
        var categories = this.fetchedCategories;
        if (!categories.length) {
            this._appendNoDataTemplate();
            return [];
        }

        // if initialCategory is archive or moved to another website
        if (categories.length && categories[0] !== this.initialCategory) {
            return [];
        } else {
            this._markUpValues(this.tpFieldsToMarkUp, data.products);
            return data.products;
        }
    },
    /**
     * @override
     */
    _setDBData: function (data) {
        var categories = _.map(this.selectionInfo.recordsIDs, function (categoryID) {
            return _.findWhere(data.categories, {id: categoryID});
        });
        this.categories = _.compact(categories);
        this.fetchedCategories = _.map(this.categories, function (category) {
            return category.id;
        });
        this.selectionInfo.recordsIDs = this.fetchedCategories;
        this._super.apply(this, arguments);
    },
});

publicWidget.registry.s_single_category_snippet = ProductRootWidget.extend(CategoryPublicWidgetMixins, MarkupRecords, {
    selector: '.s_d_single_category_snippet_wrapper',
    bodyTemplate: 's_single_category_snippet',
    bodySelector: '.s_d_single_category_snippet',
    snippetNodeAttrs: (ProductRootWidget.prototype.snippetNodeAttrs || []).concat(['data-selection-info']),
    controllerRoute: '/theme_prime/get_products_by_category',
    fieldstoFetch: ['name', 'rating', 'public_categ_ids'],
    extraLibs: (ProductRootWidget.prototype.extraLibs || []).concat(['/theme_prime/static/lib/OwlCarousel2-2.3.4/owl.carousel.js']),
    /**
     * @private
     */
    _setDBData: function (data) {
        var categories = data.categories;
        if (categories && categories.length) {
            this.categoryName = categories.length ? categories[0].name : false;
        }
        this._super.apply(this, arguments);
    },
    /**
     * initialize owlCarousel.
     * @private
     */
    _modifyElementsAfterAppend: function () {
        this._super.apply(this, arguments);
        this.initializeOwlSlider(this.uiConfigInfo.ppr);
    },
    /**
     * @private
     */
    _processData: function (data) {
        if (this.categoryName) {
            // group of 8 products
            var items = 8;
            if (config.device.isMobile || config.device.size_class === 3) {
                items = 4;
            }
            this._markUpValues(this.tpFieldsToMarkUp, data.products);
            var group = _.groupBy(data.products, function (product, index) {
                return Math.floor(index / (items));
            });
            return _.toArray(group);
        } else {
            return [];
        }
    },
    initializeOwlSlider: function () {
        this.$('.droggol_product_category_slider').owlCarousel({ dots: false, margin: 10, stagePadding: 5, rtl: _t.database.parameters.direction === 'rtl', rewind: true, nav: true, navText: ['<div class="badge text-primary"><i class="dri font-weight-bold dri-chevron-left-l"></i></div>', '<div class="badge text-primary"><i class="dri dri-chevron-right-l font-weight-bold"></i></div>'], responsive: {0: {items: 1}, 576: {items: 1}, 768: {items: 1}, 992: {items: 1}, 1200: {items: 1}}});
    }
});

// Full product snippet
publicWidget.registry.s_single_product_snippet = RootWidget.extend(ProductCarouselMixins, {
    selector: '.s_d_single_product_snippet_wrapper',

    snippetNodeAttrs: (RootWidget.prototype.snippetNodeAttrs || []).concat(['data-selection-info']),
    bodyTemplate: 's_single_product_snippet',
    controllerRoute: '/theme_prime/get_quick_view_html',
    bodySelector: '.d_single_product_continer',
    noDataTemplateString: _t("No product found"),
    noDataTemplateSubString: _t("Sorry, this product is not available right now"),
    displayAllProductsBtn: false,

    _setCamelizeAttrs: function () {
        this._super.apply(this, arguments);
        if (this.selectionInfo) {
            var productIDs = this.selectionInfo.recordsIDs;
            // first category
            if (productIDs.length) {
                this.initialProduct = productIDs[0];
            }
        }
    },
    /**
    * @private
    */
    _getOptions: function () {
        var options = {};
        if (this.initialProduct) {
            options['productID'] = this.initialProduct;
            return options;
        } else {
            return this._super.apply(this, arguments);
        }
    },
    _modifyElementsAfterAppend: function () {
        this._super.apply(this, arguments);
        this._reloadWidget({ selector: '.oe_website_sale' });
        this._bindEvents(this._getBodySelectorElement());
    },
});

// Full product snippet + cover
publicWidget.registry.s_d_single_product_cover_snippet = publicWidget.registry.s_single_product_snippet.extend({
    selector: '.s_d_single_product_cover_snippet_wrapper',

    bodyTemplate: 's_d_single_product_cover_snippet',
    bodySelector: '.s_d_single_product_cover_snippet',

    /**
    * @private
    */
    _getOptions: function () {
        var options = {};
        if (this.initialProduct) {
            options['productID'] = this.initialProduct;
            options['right_panel'] = true;
            return options;
        } else {
            return this._super.apply(this, arguments);
        }
    },
});

publicWidget.registry.s_d_top_categories = RootWidget.extend({
    selector: '.s_d_top_categories',
    bodyTemplate: 's_top_categories_snippet',
    bodySelector: '.s_d_top_categories_container',
    controllerRoute: '/theme_prime/get_top_categories',

    snippetNodeAttrs: (RootWidget.prototype.snippetNodeAttrs || []).concat(['data-selection-info', 'data-ui-config-info']),

    noDataTemplateString: _t("No categories found!"),

    noDataTemplateSubString: false,
    displayAllProductsBtn: false,

    /**
    * @private
    */
    _getOptions: function () {
        var options = {};
        if (this.selectionInfo) {
            options['params'] = {
                categoryIDs: this.selectionInfo.recordsIDs,
                sortBy: this.uiConfigInfo.sortBy,
                limit: this.uiConfigInfo.limit,
                includesChild: this.uiConfigInfo.includesChild,
            };
            return options;
        } else {
            return this._super.apply(this, arguments);
        }
    },
    _setDBData: function (data) {
        this._super.apply(this, arguments);
        var FetchedCategories = _.map(data, function (category) {
            return category.id;
        });
        var categoryIDs = [];
        _.each(this.selectionInfo.recordsIDs, function (categoryID) {
            if (_.contains(FetchedCategories, categoryID)) {
                categoryIDs.push(categoryID);
            }
        });
        this.selectionInfo.recordsIDs = categoryIDs;
    },
    /**
    * @private
    */
    _processData: function (data) {
        return _.map(this.selectionInfo.recordsIDs, function (categoryID) {
            return _.findWhere(data, {id: categoryID});
        });
    },
});

publicWidget.registry.s_d_product_count_down = ProductRootWidget.extend(ProductsBlockMixins, {
    selector: '.s_d_product_count_down',

    bodyTemplate: 's_d_product_count_down_template',

    snippetNodeAttrs: (ProductRootWidget.prototype.snippetNodeAttrs || []).concat(['data-selection-info']),

    controllerRoute: '/theme_prime/get_products_data',

    fieldstoFetch: ['name', 'description_sale', 'rating', 'public_categ_ids', 'offer_data'],

    extraLibs: (ProductRootWidget.prototype.extraLibs || []).concat(['/theme_prime/static/lib/OwlCarousel2-2.3.4/owl.carousel.js']),
    /**
     * @private
     */
    _getOptions: function () {
        var options = this._super.apply(this, arguments);
        if (this.selectionType) {
            options = options || {};
            options['shop_config_params'] = true;
        }
        return options;
    },
    /**
     * @private
     */
    _setDBData: function (data) {
        this.shopParams = data.shop_config_params;
        this._super.apply(this, arguments);
    },
    /**
     * initialize owlCarousel.
     * @private
     */
    _modifyElementsAfterAppend: function () {
        this._super.apply(this, arguments);
        this._reloadWidget({ selector: '.tp-countdown' });
        this.$('.droggol_product_slider_top').owlCarousel({
            dots: false,
            margin: 20,
            stagePadding: 5,
            rewind: true,
            rtl: _t.database.parameters.direction === 'rtl',
            nav: true,
            navText: ['<i class="dri h4 dri-chevron-left-l"></i>', '<i class="dri h4 dri-chevron-right-l"></i>'],
            responsive: {0: {items: 1}, 768: {items: 2}, 992: {items: 1}, 1200: {items: 1},
            },
        });
    },
});

publicWidget.registry.s_two_column_card_wrapper = ProductRootWidget.extend(OwlMixin, ProductsBlockMixins, {
    selector: '.s_two_column_card_wrapper',
    bodyTemplate: 'd_s_cards_wrapper',
    bodySelector: '.s_two_column_cards',
    snippetNodeAttrs: (ProductRootWidget.prototype.snippetNodeAttrs || []).concat(['data-selection-info', 'data-ui-config-info']),
    controllerRoute: '/theme_prime/get_products_data',
    fieldstoFetch: ['name', 'dr_label_id', 'rating', 'public_categ_ids', 'product_variant_ids', 'description_sale', 'colors', 'dr_stock_label'],

    _setCamelizeAttrs: function () {
        this._super.apply(this, arguments);
        if (this.uiConfigInfo) {
            this.uiConfigInfo['ppr'] = 2;
        }
        this.selectionType = false;
        if (this.selectionInfo) {
            this.selectionType = this.selectionInfo.selectionType;
        }
    },
    /**
     * initialize owlCarousel.
     * @private
     */
    _modifyElementsAfterAppend: function () {
        this._super.apply(this, arguments);
        this._reloadWidget({ selector: '.tp-product-preview-swatches'});
        if (this.uiConfigInfo.mode === 'slider') {
            this.initializeOwlSlider(this.uiConfigInfo.ppr, true);
        }
    },
});
publicWidget.registry.s_d_product_small_block = ProductRootWidget.extend(ProductsBlockMixins, {
    selector: '.s_d_product_small_block',

    bodyTemplate: 's_d_product_small_block_template',

    snippetNodeAttrs: (ProductRootWidget.prototype.snippetNodeAttrs || []).concat(['data-selection-info']),

    controllerRoute: '/theme_prime/get_products_data',

    fieldstoFetch: ['name', 'rating', 'public_categ_ids'],

    extraLibs: (ProductRootWidget.prototype.extraLibs || []).concat(['/theme_prime/static/lib/OwlCarousel2-2.3.4/owl.carousel.js']),
    /**
     * initialize owlCarousel.
     * @private
     */
    _modifyElementsAfterAppend: function () {
        var self = this;
        this._super.apply(this, arguments);
        this.inConfirmDialog = this.$el.hasClass('in_confirm_dialog');
        var numOfCol = this.inConfirmDialog ? 4 : 3;
        if (this.inConfirmDialog) {
            this.$('.owl-carousel').removeClass('container');
        }
        this.$('.droggol_product_slider_top').owlCarousel({ dots: false, margin: 20, stagePadding: this.inConfirmDialog ? 0 : 5, rewind: true, nav: true, rtl: _t.database.parameters.direction === 'rtl', navText: ['<i class="dri h4 dri-chevron-left-l"></i>', '<i class="dri h4 dri-chevron-right-l"></i>'],
            onInitialized: function () {
                var $img = self.$('.d-product-img:first');
                if (self.$('.d-product-img:first').length) {
                    $img.one("load", function () {
                        setTimeout(function () {
                            if (!config.device.isMobile) {
                                var height = self.$target.parents('.s_d_2_column_snippet').find('.s_d_product_count_down .owl-item.active .tp-side-card').height();
                                self.$('.owl-item').height(height+1);
                            }
                        }, 300);
                    });
                }
            },
            responsive: {0: {items: 2}, 576: {items: 2}, 768: {items: 2}, 992: {items: 2}, 1200: {items: numOfCol}
            },
        });
    },
});

    publicWidget.registry.s_d_image_products_block = ProductRootWidget.extend(ProductsBlockMixins, MarkupRecords, {
    selector: '.s_d_image_products_block_wrapper',
    bodyTemplate: 's_d_image_products_block_tmpl',
    snippetNodeAttrs: (ProductRootWidget.prototype.snippetNodeAttrs || []).concat(['data-selection-info']),
    bodySelector: '.s_d_image_products_block',
    controllerRoute: '/theme_prime/get_products_data',
    fieldstoFetch: ['name', 'rating', 'public_categ_ids'],
    extraLibs: (ProductRootWidget.prototype.extraLibs || []).concat(['/theme_prime/static/lib/OwlCarousel2-2.3.4/owl.carousel.js']),
    _getOptions: function () {
        return {'shop_config_params': true};
    },
    _processData: function (data) {
        var products = this._getProducts(data);
        this._markUpValues(this.tpFieldsToMarkUp, products);
        var items = 6;
        if (config.device.isMobile) {
            items = 4;
        }
        var group = _.groupBy(products, function (product, index) {
            return Math.floor(index / (items));
        });
        return _.toArray(group);
    },
    _modifyElementsAfterAppend: function () {
        this._super.apply(this, arguments);
        this.$('.droggol_product_slider_top').owlCarousel({ dots: false, margin: 10, stagePadding: 5, rewind: true, nav: true, rtl: _t.database.parameters.direction === 'rtl', navText: ['<i class="dri h4 dri-chevron-left-l"></i>', '<i class="dri h4 dri-chevron-right-l"></i>'], responsive: {0: {items: 1}, 576: {items: 1}, 768: {items: 1}, 992: {items: 1}, 1200: {items: 1}},
        });
    },
});

publicWidget.registry.s_d_products_grid_wrapper = ProductRootWidget.extend(ProductsBlockMixins, {
    selector: '.s_d_products_grid_wrapper',
    bodyTemplate: 's_d_products_grid_tmpl',
    snippetNodeAttrs: (ProductRootWidget.prototype.snippetNodeAttrs || []).concat(['data-selection-info']),
    bodySelector: '.s_d_products_grids',
    controllerRoute: '/theme_prime/get_products_data',
    fieldstoFetch: ['name', 'rating', 'public_categ_ids', 'offer_data'],
    _getOptions: function () {
        if (!this.selectionInfo) {
            return false;
        }
        return this._super.apply(this, arguments);
    },
    /**
     * initialize owlCarousel.
     * @private
     */
    _modifyElementsAfterAppend: function () {
        this._super.apply(this, arguments);
        this._reloadWidget({ selector: '.tp-countdown' });
    }
});
// Mega menus not crystal clear code :(
publicWidget.registry.s_category_tabs_snippet = RootWidget.extend({
    selector: '.s_category_tabs_snippet_wrapper',
    bodySelector: '.s_category_tabs_snippet',
    bodyTemplate: 's_category_tabs_snippet_wrapper',
    controllerRoute: '/theme_prime/get_megamenu_categories',
    snippetNodeAttrs: (RootWidget.prototype.snippetNodeAttrs || []).concat(['data-selection-info', 'data-ui-config-info']),
    read_events: _.extend({
        'mouseover .tp-menu-category-tab': '_onActivateMenuItem',
        'click .tp-menu-category-tab': '_onActivateMenuItem',
    }, RootWidget.prototype.events),

    isMobileDevice: config.device.size_class <= config.device.SIZES.MD,

    /**
     * @override
     */
    destroy: function () {
        if (this.selectionInfo && this.uiConfigInfo) {
            this._super.apply(this, arguments);
        }
    },
    /**
     * @override
     */
    _getLimit: function () {
        return this.selectionInfo && this.selectionInfo.recordsIDs ? 21 : false;;
    },
    /**
     * @override
     */
    _getOptions: function () {
        return this.selectionInfo && this.selectionInfo.recordsIDs ? { categoryIDs: this.selectionInfo.recordsIDs } : false;
    },
    /**
     * @override
     */
    _getSortBy: function () {
        return this.uiConfigInfo && this.uiConfigInfo.childOrder ? this.uiConfigInfo.childOrder : 'count';
    },
    /**
     * @private
     */
    _isActionEnabled: function (actionName, actions) {
        let allActions = actions || this.uiConfigInfo.activeActions;
        return _.contains(allActions, actionName);
    },

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * @private
     * @param categoryID {Integer} ID of category ID
     * Display submenu
     */
    _activateCategory: function (categoryID) {
        let $submenu = $(this.$(".tp-category-submenu[data-submenu-id='" + categoryID + "']"));
        this.$('.tp-category-submenu').addClass('d-none');
        $submenu.removeClass('d-none');
        if (!$submenu.hasClass('tp-fetched-submenu')) {
            this._activateCategorySubmenu($submenu);
        } else {
            this._setOffsetPosition(this.$(".tp-menu-category-tab[tp-menu-id='" + categoryID + "']"));
        }
        this.$('.tp-menu-category-tab').removeClass('tp-active-category');
        this.$(".tp-menu-category-tab[tp-menu-id='" + categoryID + "']").addClass('tp-active-category');
    },
    _isLabelActive: function () {
        return this.uiConfigInfo && this.uiConfigInfo.menuLabel;
    },
    /**
     * @private
     * @param {jQuery} $target
     */
    _activateCategorySubmenu: function ($target) {
        this._reloadWidget({ target: $target.find('> .tp-mega-menu-snippet') });
        $target.addClass('tp-fetched-submenu');
    },
    /**
     * @private
     * @param categoryID {Integer}
     * @return {Object}
     */
    getCategoryConfigData: function (categoryID) {
        if (this.uiConfigInfo && this.uiConfigInfo.categoryTabsConfig && this.uiConfigInfo.categoryTabsConfig.records) {
            let record = _.findWhere(this.uiConfigInfo.categoryTabsConfig.records || [], { id: categoryID });
            if (record) {
                record['activeActions'] = [];
                // force create activeActions array coz boolean is not acceptable
                ['brand', 'label', 'count'].forEach(actionName => {
                    if (record[actionName]) {
                        record.activeActions.push(actionName);
                    }
                });
            }
            return record;
        }
        return {};
    },
    /**
     * Set value for primary attrs
     * @private
     * @param data {Object}
     * @return {String}
     */
    _getSelectionData: function (data) {
        return JSON.stringify({ selectionType: "manual", recordsIDs: _.map(data, function (child) { return child.id }) });
    },
    /**
     * Set value for secondary attrs
     * @private
     * @param categoryID {Integer}
     * @return {Object}
     */
    _getUIConfigData: function (categoryID) {
        let { style, limit, activeActions, background, productListing } = this.getCategoryConfigData(categoryID);
        return { productListing: productListing || 'bestseller', background: background || false, style: style || 's_tp_hierarchical_category_style_1', limit: limit, activeActions: activeActions || [], model: "product.public.category" };
    },
    /**
     * @override
     */
    _modifyElementsAfterAppend: function () {
        this._super.apply(this, arguments);
        this._activateCategorySubmenu(this.$('.tp-category-submenu:not(.d-none)'));
        if (this.editableMode && this.uiConfigInfo.categoryTabsConfig && this.uiConfigInfo.categoryTabsConfig.activeRecordID) {
            this._activateCategory(this.uiConfigInfo.categoryTabsConfig.activeRecordID);
        }
    },
    /**
     * @override
     */
    _processData: function (data) {
        let result = [];
        _.each(this.selectionInfo.recordsIDs, recordsID => {
            let categoryRec = _.find(data, function (category) { return category.category.id === recordsID; });
            if (categoryRec && categoryRec.category) {
                let { child } = this.getCategoryConfigData(categoryRec.category.id);
                categoryRec['child'] = categoryRec.child.slice(0, child)
                result.push(categoryRec);
            }
        });
        return result;
    },
    /**
     * Set offset to tab
     * @private
     * @param $target {Jquery element}
     */
    _setOffsetPosition: function ($target) {
        if (this.isMobileDevice) {
            $('#top_menu_collapse').animate({
                scrollTop: $target.offset().top < 0 ? $target.offset().top : 0
            }, 0);
        }
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * @private
     * @param ev {Object} event
     */
    _onActivateMenuItem: function (ev) {
        if (this.isMobileDevice && ev.type === 'mouseover') {
            return;
        }
        let menuID = parseInt($(ev.currentTarget).attr('tp-menu-id'));
        ev.stopPropagation();
        this._activateCategory(menuID);
    },
});
publicWidget.registry.s_tp_mega_menu_category_snippet = RootWidget.extend({
    selector: '.s_tp_mega_menu_category_snippet',
    bodySelector: '.s_tp_mega_menu_category_snippet_wrapper',
    bodyTemplate: 's_tp_hierarchical_category_wrapper',
    controllerRoute: '/theme_prime/get_megamenu_categories',
    snippetNodeAttrs: (RootWidget.prototype.snippetNodeAttrs || []).concat(['data-selection-info', 'data-ui-config-info']),
    /**
     * @private
     */
    _isActionEnabled: function (actionName, actions) {
        let allActions = actions || this.uiConfigInfo.activeActions;
        return _.contains(allActions, actionName);
    },
    _getOptions: function () {
        if (this.selectionInfo && this.selectionInfo.recordsIDs) {
            return { categoryIDs: this.selectionInfo.recordsIDs};
        }
        return false;
    },
    /**
     * @override
    */
    _getSortBy: function () {
        return this.uiConfigInfo && this.uiConfigInfo.childOrder ? this.uiConfigInfo.childOrder : 'count';
    },
    destroy: function () {
        if (this.selectionInfo && this.uiConfigInfo) {
            this._super.apply(this, arguments);
        }
    },
    _getLimit: function () {
        return this.uiConfigInfo.hasOwnProperty('limit') ? this.uiConfigInfo.limit : false;
    },
    _modifyElementsAfterAppend: function () {
        this._reloadWidget({ selector: '.tp-droggol-dynamic-snippet' });
        this._reloadWidget({ selector: '.s_d_brand_snippet_wrapper' });
    },
    _getProductSelectionData: function () {
        return JSON.stringify({ selectionType: "advance", domain_params: { domain: [["public_categ_ids", "child_of", this.selectionInfo.recordsIDs]], limit: 5, order: "bestseller"} });
    },
    _getUIConfigData: function () {
        let config = {};
        config[this.uiConfigInfo.productListing] = true;
        return JSON.stringify(_.extend(config ,{'limit':3, 'style': 'tp_product_list_cards_4', 'header': 'tp_product_list_header_1', 'activeActions': ['rating', 'add_to_cart', 'wishlist', 'quick_view'], 'model': 'product.template'}))
    },
    _processData: function (data) {
        let result = this.uiConfigInfo ? [] : false;
        this.recordsIDs = [];
        _.each(this.selectionInfo.recordsIDs, recordsID => {
            let categoryRec = _.find(data, function (category) { return category.category.id === recordsID; });
            if (categoryRec) {
                result.push(categoryRec);
                this.recordsIDs.push(recordsID);
            }
        });
        return result;
    },
});
publicWidget.registry.s_category_ui_snippet = ProductRootWidget.extend(ProductsBlockMixins, {
    selector: '.s_category_snippet_wrapper',
    bodySelector: '.s_category_snippet',
    snippetNodeAttrs: (ProductRootWidget.prototype.snippetNodeAttrs || []).concat(['data-selection-info']),
    bodyTemplate: 's_tp_category_wrapper_template',
    controllerRoute: '/theme_prime/get_categories_info',
    fieldstoFetch: ['dr_category_label_id'],
    _setCamelizeAttrs: function () {
        this._super.apply(this, arguments);
        if (this.selectionInfo) {
            this.categoriesTofetch = [];
            this.categoriesTofetch = this.selectionInfo.recordsIDs;
            this.categoryStyle = this.uiConfigInfo.style;
        }
    },
    _getOptions: function () {
        return {categoryIDs: this.categoriesTofetch, getCount: true};
    },
    _processData: function (data) {
        let categories = _.map(this.categoriesTofetch, function (categoryID) {
            return _.findWhere(data, {id: categoryID});
        });
        return _.compact(categories);
    },
});

publicWidget.registry.s_d_brand_snippet = RootWidget.extend({
    selector: '.s_d_brand_snippet_wrapper',

    controllerRoute: '/theme_prime/get_brands',
    bodyTemplate: 's_d_brand_snippet',
    bodySelector: '.s_d_brand_snippet',
    fieldstoFetch: ['id', 'name', 'attribute_id'],
    displayAllProductsBtn: false,
    noDataTemplateString: _t("No brands are found!"),
    noDataTemplateSubString: _t("Sorry, We couldn't find any brands right now"),
    extraLibs: (RootWidget.prototype.extraLibs || []).concat(['/theme_prime/static/lib/OwlCarousel2-2.3.4/owl.carousel.js']),

    /**
     * @private
     */
    _getOptions: function () {
        // Hack
        this.uiConfigInfo = {};
        this.brandCount = parseInt(this.$target.get(0).dataset.brandCount);
        this.categories = this.$target.get(0).dataset.categories;
        this.mode = this.$target.get(0).dataset.mode;
        this.cardStyle = this.$target.get(0).dataset.cardStyle || 'tp_brand_card_style_1';
        return {
            limit: this.brandCount,
            categories: this.categories ? JSON.parse(this.categories) : false,
        };
    },
    _modifyElementsAfterAppend: function () {
        this._super.apply(this, arguments);
        if (this.mode === 'slider') {
            this.$('.s_d_brand_snippet > .row').addClass('owl-carousel');
            this.$('.s_d_brand_snippet > .row > *').removeAttr('class').addClass(this.cardStyle);
            // remove col-* classes
            this.$('.s_d_brand_snippet > .row > *').removeAttr('class');
            this.$('.s_d_brand_snippet > .row').removeClass('row');
            this.$('.owl-carousel').owlCarousel({ nav: false, dots:false, autoplay: true, autoplayTimeout: 4000, responsive: {0: {items: 2}, 576: {items: 4}}});
        }
    },
});

publicWidget.registry.tp_image_hotspot = publicWidget.Widget.extend(HotspotMixns, cartMixin, CartManagerMixin, {
    // V15 refector whole widget such a way that we can pass params directly in Qweb
    // <t t-if="productInfo"> is bad code

    selector: '.tp_hotspot',
    disabledInEditableMode: false,

    /**
     * @override
     */
    start: function () {
        let defs = [this._super.apply(this, arguments)];
        this.hotspotType = this.$target.get(0).dataset.hotspotType;
        this.onHotspotClick = this.$target.get(0).dataset.onHotspotClick;
        let def = this._renderHotspotTemplate();
        if (!this._isPublicUser()) {
            defs.push(def);
        }
        if (this.editableMode && this.hotspotType === 'dynamic' && this.onHotspotClick === 'modal') {
            this.$target.removeAttr('tabindex');
            this.$target.removeAttr('data-bs-toggle');
            this.$target.removeAttr('data-bs-trigger');
        } else {
            this.$target.attr({ tabindex: '0', 'data-bs-toggle': 'popover', 'data-bs-trigger': 'focus' });
        }
        return Promise.all(defs);
    },

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * This is responsible to fetch product related data.
     *
     * @returns {Promise}
     */
    _fetchData: async function () {
        return await this._rpc({
            route: '/theme_prime/get_products_data',
            params: {
                'domain': [['id', 'in', [parseInt(this.$target.get(0).dataset.productId)]]],
                'fields': ['description_sale', 'rating'],
                'limit': 1
            },
        })
    },
    /**
     * initialize popover
     */
    _initPopover: function () {
        let self = this;
        this.$target.popover({animation: true, container: 'body', html: true, placement: 'auto', content: qweb.render('theme_prime.tp_img_static_template', {widget: this, data: this._getHotspotConfig()})}).on('shown.bs.popover', function () {
            let $popover = $(window.Popover.getInstance(this).tip);
            $popover.off().on('click', '.tp-add-to-cart-action', ev => {
                self.onAddToCartClick(ev, QuickViewDialog);
            });
            $popover.addClass('tp-popover-element border-0 shadow-sm');
        });
    },
    /**
     * That's good code. isn't it? :)
     */
    _isLoaded: function () {
        return new Promise((resolve, reject) => {
            var $relatedImage = $(this.$target.closest('.tp-img-hotspot-wrapper').find(".tp-img-hotspot-enable"));
            // ImagesLazyLoading Odoo hack
            if ($relatedImage.height() > 1 && $relatedImage.width() > 0) {
                resolve();
            }
            $relatedImage.one("load", function () { resolve(); });
        });
    },
    _renderHotspotTemplate: async function () {
        if (this._isPublicUser()) {
            await this._isLoaded();
        }
        let defs = [];
        if (this.onHotspotClick === 'popover') {
            if (this.hotspotType === 'dynamic') {
                defs.push(this._fetchData())
                let [data] = await Promise.all(defs);
                this.productInfo = data.products.length ? data.products[0] : false;
                if (this.productInfo && this.productInfo.has_discounted_price) {
                    this.productInfo['discount'] = Math.round((this.productInfo.list_price_raw - this.productInfo.price_raw) / this.productInfo.list_price_raw * 100);
                }
                this._initPopover();
            }
        }
        if (this.hotspotType === 'static') {
            await Promise.all(defs);
            this._initPopover()
        }

        if (!this.editableMode) {
            this._cleanNodeAttr();
        }
    },
});

sAnimations.registry.TpHotspotScroll = sAnimations.Animation.extend({
    selector: '.tp_hotspot',
    effects: [{
        startEvents: 'scroll',
        update: '_onScroll',
    }],
    _onScroll: function (scroll) {
        if ($('.tp-popover-element:visible').length) {
            this.$target.blur();
        }
    },
});

});
