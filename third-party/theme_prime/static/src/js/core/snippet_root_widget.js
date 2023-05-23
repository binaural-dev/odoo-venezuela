odoo.define('theme_prime.root.widget', function (require) {
'use strict';

const {primeUtilities} = require('theme_prime.mixins');
const {qweb, _t} = require('web.core');
const publicWidget = require('web.public.widget');
const config = require('web.config');

let ThemePrimeRootWidget = publicWidget.Widget.extend(primeUtilities, {
    disabledInEditableMode: false,
    controllerRoute: false,
    fieldstoFetch: false,
    bodyTemplate: false,
    bodySelector: false,
    displayLoader: true,
    snippetNodeAttrs: [],
    extraLibs: [],
    IsAttrSet: false,

    // Droggol's attributs :)
    noDataTemplate: 'droggol_default_no_data_templ',
    noDataTemplateImg: '/theme_prime/static/src/img/no_data.svg',
    noDataTemplateString: _t("No products found!"),
    noDataTemplateSubString: _t("Sorry, We couldn't find any products"),
    displayAllProductsBtn: true,
    loaderTemplate: 'droggol_default_loader',
    isMobile: config.device.isMobile,
    /**
     * @override
     */
    start: function () {
        let defs = [this._super.apply(this, arguments)];
        // Remove this code in next version
        if (this.$target.hasClass('droggol_product_snippet') || this.$target.hasClass('tp-dynamic-snippet')) {
            this._renderAndAppendQweb('tp_block_deprecated_notice', 'tp_block_deprecated_notice', true);
            return Promise.all(defs);
        }
        this._setCamelizeAttrs();
        if (!this.IsAttrSet && this.$target.hasClass('tp-mega-menu-snippet')) {
            return Promise.all(defs);
        }
        let params = this._getParameters();
        if (this.controllerRoute && !_.isEmpty(params)) {
            if (this.fieldstoFetch) {
                _.extend(params, {fields: this._getFieldsList()});
            }
            this._onResizeChange = _.debounce(this._onWindowResize, 100);
            $(window).resize(() => {
                this._onResizeChange();
            });
            let def = this._renderPrimeTemplate(params);
            if (!this._isPublicUser()) {
                defs.push(def);
            }
            return Promise.all(defs);
        }
        return Promise.all(defs);
    },
    /**
    * @override
    */
    destroy: function () {
        if (!this.IsAttrSet && this.$target.hasClass('tp-mega-menu-snippet')) {
            return this._super.apply(this, arguments);
        }
        this.options.wysiwyg && this.options.wysiwyg.odooEditor.observerUnactive();
        this._super.apply(this, arguments);
        this._modifyElementsBeforeRemove();
        this._getBodySelectorElement().empty();
        this.options.wysiwyg && this.options.wysiwyg.odooEditor.observerActive();
    },
    /**
     * No need to return promise here for the moment we are not using it anywhere but we might need it in future :)
     */
    _reloadWidget: async function (data) {
        let {selector, target} = data;
        if (!target && selector && !this.$target.find(selector).length) {
            return;
        } else {
            target = target ? target : this.$target.find(selector);
        }
        return new Promise((resolve, reject) => {
            this.trigger_up('widgets_start_request', { editableMode: this.editableMode, $target: target, onSuccess: resolve, onFailure: reject});
        });
    },
    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
    * @private
    */
    _appendLoader: function () {
        if (this.displayLoader && this.loaderTemplate) {
            this._renderAndAppendQweb(this.loaderTemplate, 'd_loader_default', true);
        }
    },
    /**
     * @private
     */
    _appendNoDataTemplate: function () {
        if (this.noDataTemplate) {
            this._renderAndAppendQweb(this.noDataTemplate, 'd_no_data_tmpl_default', true);
        }
    },
    /**
     * @private
     */
    _cleanBeforeAppend: function () {
        // Remove unecessary elements
        this.$('.d_loader_default').remove();
        this.$('.d_no_data_tmpl_default').remove();
        this.$('.d_editor_tmpl_default').remove();
    },
    /**
     * @private
     */
    _cleanAttributes: function () {
        if (this._isPublicUser()) {
            this.snippetNodeAttrs.forEach(attr => {
                this.$target.removeAttr(attr);
            });
        }
    },
    /**
     * @private
     */
    _isElementInViewport: function () {
        var windowHeight = window.innerHeight || document.documentElement.clientHeight || document.body.clientHeight;
        return (this.$target.offset().top - windowHeight) < 350;
    },
    /**
     * @private
     */
    _getBodySelectorElement: function () {
        let selector = this.bodySelector;
        return selector ? this.$(selector) : this.$target;
    },
    /**
    * @private
    */
    _getDomain: function () {
        return false;
    },
    /**
    * @private
    */
    _getFieldsList: function () {
        return this.fieldstoFetch;
    },
    /**
    * @private
    */
    _getLimit: function () {
        return false;
    },
    /**
     * @private
     */
    _getOptions: function () {
        return false;
    },
    /**
     * @private
     */
    _getSortBy: function () {
        return false;
    },
    /**
     * @private
     */
    _getParameters: function () {
        let domain = this._getDomain();
        let params = {};
        if (domain) {
            params['domain'] = domain;
        }
        let limit = this._getLimit();
        if (limit !== false) {
            params['limit'] = limit;
        }
        let order = this._getSortBy();
        if (order) {
            params['order'] = order;
        }
        let options = this._getOptions();
        if (options) {
            params['options'] = options;
        }
        return params;
    },
    /**
     * @private
     */
    _isPublicUser: function () {
        return _.has(odoo.dr_theme_config, "is_public_user") && odoo.dr_theme_config.is_public_user;
    },
    /**
     * @private
     */
    _onSuccessResponse: function (response) {
        let hasData = this._responseHasData(response);
        if (hasData) {
            this._setDBData(response);
            this._renderContent(this._processData(response));
        } else {
            this._appendNoDataTemplate();
        }
    },
    /**
     * @private
     */
    _fetchData: async function (params) {
        return await this._rpc({route: this.controllerRoute, params: params});
    },
    /**
     * @private
     */
    _isReadyToFetch: async function () {
        this.$megaMenu = this.$el.closest('.dropdown');
        return new Promise((resolve, reject) => {
            this.$relativeTarget = $('#wrapwrap'); // #wrapwrap for now bcoz window is not scrolleble in v14
            var position = this.$relativeTarget.scrollTop();
            if (this.$megaMenu.length) {
                // throttle needed otherwise sometimes it's crash the chrome :)
                this.$megaMenu.on('show.bs.dropdown show.tp.dropdown', _.throttle(ev => { resolve()}, 200));
            } else {
                this.$relativeTarget.on('scroll.snippet_root_scroll', _.throttle(ev => {
                    var scroll = this.$relativeTarget.scrollTop();
                    if (scroll > position) {
                        // Trigger only when scrollDown
                        if (this._isElementInViewport(this.target)) {
                            resolve();
                        }
                    }
                    position = scroll;
                }, 200));
            }
        });
    },
    /**
     * @private
     */
    _modifyElementsBeforeRemove: function () {},
    /**
     * @private
     */
    _modifyElementsAfterAppend: function () {
        this.$('.d_body_tmpl_default').removeClass('d_body_tmpl_default');
        this._cleanAttributes();
    },
    /**
     * @private
     */
    _processData: function (data) {
        return data;
    },
    /**
     * @private
     */
    _responseHasData: function (data) {
        return data;
    },
    /**
     * @private
     */
    _setCamelizeAttrs: function () {
        let snippetNodeAttrs = this.snippetNodeAttrs;
        snippetNodeAttrs.forEach(attr => {
            let str = attr.startsWith('data-') ? attr.split('data-') : attr;
            let arr = str[1].split('-');
            let capital = arr.map((item, index) => index ? item.charAt(0).toUpperCase() + item.slice(1).toLowerCase() : item.toLowerCase());
            // ^-- fuck this below shit here
            // If you didn't get this thing then ask to boy Kishan Gajjar (kig-odoo)
            let capitalString = capital.join("");
            let attrVal = this.$target.get(0).dataset[capitalString];
            this[capitalString] = attrVal !== undefined ? JSON.parse(attrVal) : false;
            this[`${capitalString}_init`] = attrVal !== undefined ? JSON.parse(attrVal) : false;
            if (this[capitalString]) {
                this.IsAttrSet = true;
            }
        });
    },
    /**
     * @private
     * override to set values to widget
     */
    _setDBData: function (data) {},
    /**
     * @private
     */
    _renderAndAppendQweb: function (template, className, data) {
        // observer shit needed but wait for someone to report a bug don't want to spread shit here
        if (!template || !data) {
            // for safety
            return;
        }
        let $template = $(qweb.render(template, {data: data, widget: this}));
        $template.addClass(className);
        // html() make sure template appends only once.
        this._getBodySelectorElement().html($template);
    },
    /**
     * @private
     */
    _renderContent: function (data) {
        // Should remove this below observer shit someday we need to rework on few things.
        // May be we might remove publicWidget it self and implementation our own way to render snippet
        // In this particular version 16.0 publicWidget is bit changed.
        // But any way thanks to Quentin for everything :)
        this.options.wysiwyg && this.options.wysiwyg.odooEditor.observerUnactive();
        this._cleanBeforeAppend();
        this._renderAndAppendQweb(this.bodyTemplate, 'd_body_tmpl_default', data);
        this._modifyElementsAfterAppend();
        this.options.wysiwyg && this.options.wysiwyg.odooEditor.observerActive();
    },
    /**
    * @private
    */
    _onWindowResize: function () {},
    /**
     * @private
     * Happy debugging suckers
     */
    _renderPrimeTemplate: async function (params) {
        if (this.$target.hasClass('tp-snippet-shiftless-enable') && this._isPublicUser()) {
            await this._isReadyToFetch();
        }
        // for safety to avoid crash
        let [response, anotherResult] = await Promise.all([this._fetchData(params), this._primeLoadExtras(this._appendLoader.bind(this))]);
        this.response = response;
        this._onSuccessResponse(response);
        return response;
    },
});

publicWidget.registry.tp_root_widget = ThemePrimeRootWidget;

return ThemePrimeRootWidget;
});
