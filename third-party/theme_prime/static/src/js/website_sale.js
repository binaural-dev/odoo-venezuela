/** @odoo-module **/

import "website_sale.website_sale";
import "@website_sale_stock_wishlist/js/website_sale";
import concurrency from "web.concurrency";
import publicWidget from "web.public.widget";
import sAnimations from "website.content.snippets.animation";
import Dialog from "web.Dialog";
import config from "web.config";
import utils from "web.utils";
import { ProductCarouselMixins } from "theme_prime.mixins";
import { Sidebar } from "@theme_prime/js/sidebar";
import { qweb, _t } from "web.core";

const isMobileEnv = config.device.size_class <= config.device.SIZES.LG && config.device.touch;

// FIXME: JAT
// Bottombar's filter is outside of public widget so it's hard to communicate and maintain state.
// This variable should be inside public widget and _onClickOpenFilterSidebar method should use DOM elements of widget itself not global.
let filterSidebarInstance = false;

publicWidget.registry.WebsiteSale.include({
    jsLibs: (publicWidget.registry.WebsiteSale.prototype.jsLibs || []).concat(
        ['/theme_prime/static/lib/drift-master-1.5.0/dist/Drift.js'],
    ),
    cssLibs: (publicWidget.registry.WebsiteSale.prototype.cssLibs || []).concat(
        ['/theme_prime/static/lib/drift-master-1.5.0/dist/drift-basic.css'],
    ),
    events: Object.assign({}, publicWidget.registry.WebsiteSale.prototype.events || {}, {
        'click .tp-attribute': '_onClickAttribute',
        'input .tp-search-attribute-value': '_onChangeSearchAttributeValue',
        'click .tp-filter-attribute-title.collapsible': '_onClickFilterAttributeTitle',
        'submit form.js_attributes': '_onFormSubmit',
        'click .tp-open-filter-sidebar': '_onClickOpenFilterSidebar',
        "click .tp-load-more-btn": "_onClickLoadMoreBtn",
        'click [data-link-href]': '_openLink',
        "click .tp-action-buttons-toggler": "_onClickActionButtonsToggler",
    }),
    init: function () {
        this._super.apply(this, arguments);
        this.isLazyLoad = odoo.dr_theme_config.json_shop_layout.layout == "prime" && odoo.dr_theme_config.json_shop_filters.lazy_method;
        this.selectorToReplace = ['.tp-category-pill-container', '.tp-shop-topbar', '.tp-shop-row'];
        this.classToIgnore = ['tp-search-attribute-value', 'tp-slider'];
        this.driftImages = [];
        this.dp = new concurrency.DropPrevious();
        $('.tp-filter-bottom-sidebar-toggle').off().on('click', this._onClickOpenFilterSidebar.bind(this)); // JAT: To work for bottombar
    },
    start() {
        if (this.el.classList.contains("tp-shop-layout") && this.isLazyLoad) {
            window.addEventListener('popstate', this._handleBackNavigation);
        }
        if (this.el.querySelector(".tp-load-more-on-scroll")) {
            this.loadMoreObserver = new IntersectionObserver(entries => {
                entries.forEach((entry) => {
                    if (entry.intersectionRatio > 0) {
                        this._loadMoreProducts(this.el.querySelector(".tp-load-more-on-scroll").getAttribute("href"));
                        this.el.querySelector(".tp-load-more-on-scroll").remove();
                    }
                })
            }, {});
            this.loadMoreObserver.observe(this.el.querySelector(".tp-load-more-on-scroll"));
        }
        return this._super(...arguments);
    },
    _startZoom: function () {
        const namespace = _t.database.parameters.direction === "rtl" ? "tp-rtl" : "tp";
        const zoomConfig = odoo.dr_theme_config.json_zoom;
        if (zoomConfig.zoom_enabled) {
            const images = this.el.querySelectorAll("img[data-zoom]");
            for (const image of images) {
                image.classList.add("cursor-pointer");
                const imageVals = { namespace: namespace, sourceAttribute: "src", inlineOffsetY: -50, paneContainer: image.parentElement, zoomFactor: zoomConfig.zoom_factor || 2, inlinePane: 992, touchDelay: 500 };
                const zoomImage = image.dataset.zoomImage;
                if (zoomImage) {
                    imageVals.sourceAttribute = "data-zoom-image";
                    this.driftImages.push(new Drift(image, imageVals));
                }
            }
        } else {
            this._super(...arguments);
        }
    },
    _onChangeCombination: function (ev, $parent, combination) {
        this._super.apply(this, arguments);
        // Stick add to cart
        const $stickyAddToCart = $('.tp-sticky-add-to-cart, .tp-bottom-bar-add-to-cart');
        if ($stickyAddToCart.length) {
            $stickyAddToCart.find('.oe_currency_value').text(this._priceToStr(combination.price));
            $stickyAddToCart.find('.product-img').attr('src', '/web/image/product.product/' + combination.product_id + '/image_128');
            $stickyAddToCart.find('.product-add-to-cart').removeClass('disabled');
            if (['always', 'threshold'].includes(combination.inventory_availability)) {
                if (!combination.virtual_available) {
                    $stickyAddToCart.find('.product-add-to-cart').addClass('disabled');
                }
            }
        }
        // Discount percentage
        const $price = $parent.find('.product_price h3.css_editable_mode_hidden');
        let $percentage = $parent.find('.tp-discount-percentage');
        if (combination.has_discounted_price) {
            const percentage = Math.round((combination.list_price - combination.price) / combination.list_price * 100);
            if (percentage) {
                const percentageText = _.str.sprintf(_t('(%d%% OFF)'), percentage);
                if ($percentage.length) {
                    $percentage.text(percentageText);
                } else {
                    $percentage = $('<small class="tp-discount-percentage d-none d-md-inline-block ms-1">' + percentageText + '</small>');
                    $percentage.appendTo($price);
                }
            } else {
                $percentage.remove();
            }
        } else {
            $percentage.remove();
        }

        if (combination.tp_extra_fields) {
            const $productContainer = $parent.closest('tr.js_product, .oe_website_sale, .o_product_configurator');
            const $extraFields = $productContainer.find('.tp_extra_fields');
            $extraFields.replaceWith($(combination.tp_extra_fields));
        }
    },
    _updateProductImage: function ($productContainer, displayImage, productId, productTemplateId, newImages, isCombinationPossible) {
        if ($productContainer.hasClass('auto-add-product')) {
            return;
        }
        let $images = $productContainer.find(this._getProductImageContainerSelector());
        if ($images.length && !this._isEditorEnabled()) {
            const $newImages = $(newImages);
            $images.after($newImages);
            $images.remove();
            $images = $newImages;
            if ($images.attr('id') === 'o-carousel-product') {
                $images.carousel(0);
            }
            this._startZoom();
            // fix issue with carousel height
            this.trigger_up('widgets_start_request', {$target: $images});
            ProductCarouselMixins._bindEvents($productContainer);  // Hook
        }
        $images.toggleClass('css_not_available', !isCombinationPossible);

        // For left panel dynamic snippet
        const $container = $productContainer.parents('.tp-show-variant-image');
        if ($container.length) {
            const imageEl = $container.find('.tp-variant-image')[0];
            const src = $images.find('.product_detail_img').first().attr('src');
            if (src !== imageEl.src) {
                imageEl.classList.remove("tp-product-image-fade-animation");
                imageEl.src = src;
                imageEl.addEventListener('load', () => {
                    imageEl.classList.add("tp-product-image-fade-animation");
                }, { once: true });
            }
        }
    },
    _onClickOpenFilterSidebar: function (ev) {
        ev.preventDefault();
        // Clear sliders
        $(".tp-slider").each(function () {
            $(this).data("ionRangeSlider").destroy();
        });

        const sidebarHtml = qweb.render("theme_prime.ShopFilterSidebar", { content: utils.Markup($(".tp-filters-container")[0].innerHTML) });
        return new Sidebar(this, {
            title: _t("Filters"),
            icon: "fa fa-filter",
            class: "tp-shop-filter-sidebar",
            contentHtml: sidebarHtml,
            parentSelector: ".oe_website_sale",
            position: "start",
        }).show().then(instance => {
            filterSidebarInstance = instance;
            this.trigger_up("widgets_start_request", {
                $target: $(".tp-filter-attribute"),
            });
        });
    },
    _onClickAttribute: function (ev) {
        if (ev.currentTarget.classList.contains("clear")) {
            this.el.querySelectorAll(".tp-attribute").forEach(el => {
                this._deactivateFilter(el);
            });
        } else {
            this._deactivateFilter(ev.currentTarget);
        }
        this.$("form.js_attributes").submit();
    },
    _deactivateFilter: function (el) {
        const { id, type } = el.dataset;
        if (type === "price") {
            if (this.el.querySelector(".js_attributes input[name=min_price]")) {
                this.el.querySelector(".js_attributes input[name=min_price]").remove();
            }
            if (this.el.querySelector(".js_attributes input[name=max_price]")) {
                this.el.querySelector(".js_attributes input[name=max_price]").remove();
            }
        }
        const inputEl = this.el.querySelector(`.js_attributes input[id=${id}]`);
        if (inputEl) {
            inputEl.checked = false;
        }
        const optionEl = this.el.querySelector(`.js_attributes option[id=${id}]`);
        if (optionEl) {
            optionEl.closest("select").value = "";
        }
    },
    _onClickSubmitWishlistStockNotificationForm(ev) {
        // From module: website_sale_stock_wishlist
        const productId = JSON.parse(ev.currentTarget.closest('.tp-wishlist-item').dataset.productTrackingInfo).item_id;
        this._handleClickSubmitStockNotificationForm(ev, productId);
    },
    _onChangeSearchAttributeValue: function (ev) {
        ev.stopPropagation();
        const value = ev.currentTarget.value.trim();
        if (value) {
            this.el.querySelectorAll('li[data-search-term]').forEach(el => {
                el.classList.add('d-none');
            });
            this.el.querySelectorAll('li[data-search-term*="' + value.toLowerCase() + '"]').forEach(el => {
                el.classList.remove('d-none');
            });
        } else {
            this.el.querySelectorAll('li[data-search-term]').forEach(el => {
                el.classList.remove('d-none');
            });
        }
    },
    _onClickFilterAttributeTitle: function (ev) {
        if ($(ev.currentTarget).hasClass('expanded')) {
            $(ev.currentTarget).siblings('.tp-filter-attribute-collapsible-area').slideUp('fast');
        } else {
            $(ev.currentTarget).siblings('.tp-filter-attribute-collapsible-area').slideDown('fast');
        }
        $(ev.currentTarget).toggleClass('expanded');
    },
    _onChangeAttribute: function (ev) {
        if (![...ev.currentTarget.classList].some(className => this.classToIgnore.indexOf(className) !== -1)) {
            this._super.apply(this, arguments);
        }
    },
    _openLink: function (ev) {
        ev.preventDefault();
        if (this.isLazyLoad) {
            this._replaceContent(ev.currentTarget.getAttribute('data-link-href'));
        } else {
            window.location.href = ev.currentTarget.getAttribute('data-link-href');
        }
    },
    _onFormSubmit: function (ev) {
        if (this.isLazyLoad) {
            ev.preventDefault();
            const $form = $(ev.currentTarget).closest('form');
            const url = window.location.pathname + '?' + $form.serialize();
            this._replaceContent(url);
        }
    },
    _replaceContent: function (url) {
        document.getElementById('wrapwrap').scrollTo({top: 0, behavior: 'smooth'});
        if (filterSidebarInstance) {
            filterSidebarInstance.hide();
        }
        this.$('#products_grid').empty();
        this.$shopLoader = $(qweb.render('theme_prime.Loader'));
        this.$shopLoader.appendTo(this.$('#products_grid'));
        window.history.pushState({}, '', url);
        this.dp.add(
            new Promise(function (resolve, reject) {
                $.ajax({
                    url: url,
                    type: 'GET',
                    success: function (data) {
                        resolve(data);
                    }
                });
            })
        ).then(data => {
            this._replaceShopContent(data);
            this.trigger_up('widgets_start_request', {
                $target: this.$el,
            });
        });
    },
    _onClickLoadMoreBtn: function (ev) {
        ev.preventDefault();
        this._loadMoreProducts(ev.currentTarget.getAttribute("href"));
        ev.currentTarget.remove();
    },
    _loadMoreProducts: function (url) {
        this.$shopLoader = $(qweb.render("theme_prime.Loader", { height: "20vh" }));
        this.$shopLoader.appendTo(this.$(".tp-product-pager"));
        this.dp.add(
            new Promise((resolve, reject) => {
                $.ajax({
                    url: url,
                    type: "GET",
                    success: data => {
                        resolve(data);
                    }
                });
            })
        ).then(data => {
            $(data).find(".tp-product-item").insertAfter(this.$(".tp-product-item:last"));
            this.$(".tp-product-pager").replaceWith($(data).find(".tp-product-pager"));
            this.trigger_up("widgets_start_request", {
                $target: this.$el,
            });
        });
    },
    _replaceShopContent: function (data) {
        this.selectorToReplace.forEach(selector => {
            this.$(selector).replaceWith($(data).find(selector));
        });
    },
    _handleBackNavigation: function (event) {
        window.location.reload();
    },
    _setUrlHash: function ($parent) {
        if (!this.el.classList.contains("tp-noupdate-variant-change-url")) {
            return this._super.apply(this, arguments);
        }
    },
    _onClickActionButtonsToggler: function (ev) {
        this.el.querySelectorAll('.tp-action-buttons-toggler').forEach(el => {
            el.classList.remove("d-none");
        });
        this.el.querySelectorAll('.tp-action-toggle').forEach(el => {
            el.classList.add("d-none");
        });
        ev.currentTarget.classList.add("d-none");
        ev.currentTarget.parentElement.querySelectorAll('.tp-action-toggle').forEach(el => {
            el.classList.toggle("d-none");
        });
    },
    destroy: function () {
        window.removeEventListener('popstate', this._handleBackNavigation);
        if (this.loadMoreObserver && this.el.querySelector(".tp-load-more-on-scroll")) {
            this.loadMoreObserver.unobserve(this.el.querySelector(".tp-load-more-on-scroll"));
        }
        this.driftImages.forEach(drift => { drift.disable() });
        this._super.apply(this, arguments);
    },
});

//------------------------------------------------------------------------------
// Shop Page
//------------------------------------------------------------------------------
sAnimations.registry.TpShopButtons = sAnimations.Animation.extend({
    selector: ".tp-shop-page",
    effects: [{
        startEvents: "scroll",
        update: "_onScroll",
    }],
    _onScroll: function () {
        document.querySelectorAll(".tp-action-buttons-toggler").forEach(el => {
            el.classList.remove("d-none");
        });
        document.querySelectorAll(".tp-action-toggle").forEach(el => {
            el.classList.add("d-none");
        });
    },
});

publicWidget.registry.TpRangeFilter = publicWidget.Widget.extend({
    selector: '.tp-range-filter',
    jsLibs: ['/theme_prime/static/lib/ion.rangeSlider-2.3.1/js/ion.rangeSlider.js'],
    cssLibs: ['/theme_prime/static/lib/ion.rangeSlider-2.3.1/css/ion.rangeSlider.css'],
    events: {
        'change input.min': '_onChangeInput',
        'change input.max': '_onChangeInput',
        'click .apply': '_onClickApply',
    },
    start: function () {
        this.$slider = this.$('.tp-slider');
        this.$slider.ionRangeSlider({
            skin: 'square',
            prettify_separator: ',',
            type: 'double',
            hide_from_to: true,
            onChange: ev => {
                this.$('input.min').val(ev.from);
                this.$('input.max').val(ev.to);
                this.$('.tp-validate-msg').text('');
                this.$('.apply').removeClass('d-none');
            },
        });
        this.key = this.$slider.data('key');
        this.slider = this.$slider.data('ionRangeSlider');
        return this._super.apply(this, arguments);
    },
    _onChangeInput: function (ev) {
        ev.preventDefault();
        const minValue = this.$('input.min').val();
        const maxValue = this.$('input.max').val();

        if (isNaN(minValue) || isNaN(maxValue)) {
            this.$('.tp-validate-msg').text(_t('Enter valid value.'));
            this.$('.apply').addClass('d-none');
            return false;
        }
        if (parseInt(minValue) > parseInt(maxValue)) {
            this.$('.tp-validate-msg').text(_t('Maximum value should be greater than minimum.'));
            this.$('.apply').addClass('d-none');
            return false;
        }
        this.slider.update({
            from: minValue,
            to: maxValue,
        });
        this.$('.tp-validate-msg').text('');
        this.$('.apply').removeClass('d-none');
        return false;
    },
    _onClickApply: function (ev) {
        this.$('input[name=min_' + this.key + ']').remove();
        this.$('input[name=max_' + this.key + ']').remove();
        if (this.slider.result.from !== this.slider.result.min) {
            this.$el.append($('<input>', {type: 'hidden', name:'min_' + this.key, value: this.slider.result.from}));
        }
        if (this.slider.result.to !== this.slider.result.max) {
            this.$el.append($('<input>', {type: 'hidden', name:'max_' + this.key, value: this.slider.result.to}));
        }
    },
    destroy: function () {
        this._super.apply(this, arguments);
        this.slider.destroy();
    }
});

publicWidget.registry.TpProductPreviewSwatches = publicWidget.Widget.extend({
    selector: ".tp-product-preview-swatches",
    events: {
        "mouseenter .tp-swatch:not(.more)": "_onMouseEnterSwatch",
        "mouseleave": "_onMouseLeave",
    },
    start: function () {
        this.imageEl = this.el.closest(this.el.dataset.parentSelector).querySelector(this.el.dataset.imgSelector);
        return this._super.apply(this, arguments);
    },
    _onMouseEnterSwatch: function (ev) {
        this._updateImgSrc(ev.currentTarget.dataset.previewImgSrc);
        ev.currentTarget.classList.add("active");
    },
    _onMouseLeave: function () {
        this._updateImgSrc();
    },
    _updateImgSrc: function (src=false) {
        this.imageEl.classList.remove("tp-product-preview-active");
        this.el.querySelectorAll(".tp-swatch").forEach((el, index) => {
            el.classList.remove("active");
        });
        this.imageEl.src = src || this.el.dataset.defaultImgSrc;
        this.imageEl.addEventListener('load', () => {
            if (src) {
                this.imageEl.classList.add("tp-product-preview-active");
            }
        }, { once: true });
    },
});

//------------------------------------------------------------------------------
// Product Detail Page
//------------------------------------------------------------------------------
publicWidget.registry.websiteSaleCarouselProduct.include({
    _updateJustifyContent: function () {
        this._super.apply(this, arguments);
        const indicatorsDivEl = this.target.querySelector('.carousel-indicators');
        if (indicatorsDivEl) {
            indicatorsDivEl.style['justify-content'] = 'center';
        }
    },
});

publicWidget.registry.TpProductDetailPage = publicWidget.Widget.extend({
    selector: '.o_wsale_product_page',
    events: {
        'click .o_product_page_reviews_link': '_onClickProductRating',
    },
    start: function () {
        this.popovers = [];
        this.el.querySelectorAll('.tp-navigation-btn').forEach((el, index) => {
            const popoverEl = this.el.querySelector(`.tp-navigation-content[data-content-id=${el.dataset.contentId}]`);
            if (popoverEl) {
                const clonePopoverEl = popoverEl.cloneNode(true);
                clonePopoverEl.classList.remove('d-none');
                const popover = new Popover(el, {
                    animation: true,
                    template: '<div class="popover border shadow-sm" role="popover"><div class="popover-arrow"></div><div class="popover-body p-0"></div></div>',
                    content: clonePopoverEl.outerHTML,
                    html: true,
                    placement: 'bottom',
                    trigger: 'hover',
                    offset: [8, 8],
                });
                this.popovers.push(popover);
            }
        });

        const productDetailTabEl = this.el.querySelector('.tp-product-details-tab');
        productDetailTabEl.querySelectorAll(':scope > ul.nav-tabs a.nav-link').forEach(el => {
            el.classList.remove('active');
        });
        productDetailTabEl.querySelectorAll(':scope > .tab-content > .tab-pane').forEach(el => {
            el.classList.remove('active', 'show');
        });
        const firstTabEl = productDetailTabEl.querySelector(':scope > ul.nav-tabs > li.nav-item:first-child > a.nav-link');
        if (firstTabEl) {
            new Tab(firstTabEl).show();
        }
        return this._super.apply(this, arguments);
    },
    _onClickProductRating: function () {
        const ratingTabEl = this.el.querySelector('[href="#tp-product-rating-tab"]')
        new Tab(ratingTabEl).show();
        document.querySelector('#wrapwrap').scrollTop = ratingTabEl.offsetTop;
    },
    destroy: function () {
        this.popovers.forEach(popover => { popover.dispose() });
        this._super.apply(this, arguments);
    }
});

publicWidget.registry.TpLazyDialog = publicWidget.Widget.extend({
    selector: '.tp-lazy-dialog',
    events: {
        'click': '_onClick',
    },
    init: function () {
        this.dialogContent = false;
        this._super.apply(this, arguments);
    },
    _onClick: async function (ev) {
        ev.preventDefault();
        const { resId, resModel, field } = this.el.dataset;
        if (!this.dialogContent) {
            const result = await this._rpc({
                route: '/theme_prime/get_dialog_content',
                params: {
                    res_id: resId,
                    res_model: resModel,
                    fields: [field],
                },
            });
            if (result && result[0][field]) {
                this.dialogContent = result[0][field];
            }
        }
        this.dialog = new Dialog(this, {
            technical: false,
            $content: $('<div/>').html(this.dialogContent),
            dialogClass: 'p-0',
            renderFooter: false,
        }).open();
        this.dialog.opened().then(() => {
            this.dialog.$modal.find('.modal-dialog').addClass('modal-dialog-centered');
            this.dialog.$modal.addClass('tp-lazy-dialog-modal');
            this.trigger_up('widgets_start_request', {
                $target: this.dialog.$modal,
                editableMode: this.editableMode
            });
        });
    },
});

sAnimations.registry.TpStickyAddToCart = sAnimations.Animation.extend({
    selector: '.tp-sticky-add-to-cart, .tp-bottom-bar-add-to-cart',
    disabledInEditableMode: true,
    effects: [{
        startEvents: 'scroll',
        update: '_onScroll',
    }],
    events: {
        'click .product-add-to-cart': '_onClickProductAddToCart',
        'click .product-img': '_onClickImg'
    },
    _onScroll: function () {
        if (!isMobileEnv && $('#add_to_cart').length) {
            if ($('#add_to_cart')[0].getBoundingClientRect().top <= 0) {
                this.$el.fadeIn();
            } else {
                this.$el.fadeOut();
            }
        }
    },
    _onClickProductAddToCart: function (ev) {
        ev.preventDefault();
        let $btn = $('#add_to_cart:not(".disabled")');
        if ($btn.length) {
            const event = new MouseEvent('click', { view: window, bubbles: true });
            $btn[0].dispatchEvent(event);
        }
    },
    _onClickImg: function (ev) {
        ev.preventDefault();
        $('html, body').animate({ scrollTop: 0 });
    }
});

//------------------------------------------------------------------------------
// Brand Page
//------------------------------------------------------------------------------
publicWidget.registry.TpBrandPage = publicWidget.Widget.extend({
    selector: '.tp-all-brands-page',
    events: {
        'click .tp-brand-search-alphabet': '_onClickBrandSearchAlphabet',
    },
    _onClickBrandSearchAlphabet: function (ev) {
        this.el.querySelectorAll('.tp-brand-search-alphabet').forEach(el => {
            el.classList.remove('active');
        });
        ev.currentTarget.classList.add('active');
        const searchAlphabet = ev.currentTarget.dataset.alphabet;
        if (searchAlphabet === 'all') {
            this.el.querySelectorAll('.tp-grouped-brands').forEach(el => {
                el.classList.remove('d-none');
            });
        } else {
            this.el.querySelectorAll('.tp-grouped-brands').forEach(el => {
                el.classList.add('d-none');
            });
            this.el.querySelector('.tp-grouped-brands[data-brand="' + searchAlphabet + '"]').classList.remove('d-none');
        }
    }
});
