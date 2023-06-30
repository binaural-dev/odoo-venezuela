/** @odoo-module **/

import { WebsiteDialog } from '@website/components/dialog/dialog';
import { evaluateExpr } from "@web/core/py_js/py";

const { Component, useState, onWillStart, onWillUpdateProps, toRaw } = owl;
import { useService } from '@web/core/utils/hooks';
import { useCore } from '@droggol_theme_common/js/hooks';

import { _t } from 'web.core';


export class AbstractThemeOption extends Component {
    setup() {
        this.key = this.props.key;
        onWillUpdateProps(nextProps => {
            this.updateVal(nextProps);
        });
    }
    updateVal (props) {
        if (props.visibilityExpr) {
            props['visibility'] = evaluateExpr(props.visibilityExpr, props.source)
        }
        this.env.updateConfigValue(this.key, props.value)
    }
    updateSource (value) {
        this.env.updateSource(this.key, value)
    }
}

export class ThemeOptionTitle extends AbstractThemeOption {}
ThemeOptionTitle.template = 'theme_config.ThemeOptionTitle';

export class ThemeOptionRadio extends AbstractThemeOption {}
ThemeOptionRadio.template = 'theme_config.ThemeOptionRadio';

export class ThemeOptionSelection extends AbstractThemeOption {}
ThemeOptionSelection.template = 'theme_config.Selection';

export class ThemeOptionCheckbox extends AbstractThemeOption {}
ThemeOptionCheckbox.template = 'theme_config.Checkbox';

export class ThemeOptionCardBtnCheckbox extends AbstractThemeOption {}
ThemeOptionCardBtnCheckbox.template = 'theme_config.BtnCheckbox';

export class ThemeOptionNumber extends AbstractThemeOption {}
ThemeOptionNumber.template = 'theme_config.Number';

export class ThemeOptionChar extends AbstractThemeOption {}
ThemeOptionChar.template = 'theme_config.Char';

export class ThemeOptionJson extends AbstractThemeOption {
    setup() {
        super.setup();
        this.updatedValue = this.props.value;
        this._coreProps = {
            updateConfigValue: this.updateConfigValue.bind(this),
            updateSource: this.updateSource.bind(this),
        };
        useCore({subMode: true});
    }
    prepareProps (self_props, sub_props) {
        var props = sub_props || {};
        props['visibility'] = true;
        props['source'] = self_props.source[self_props.key];
        if (props.visibilityExpr) {
            props['visibility'] = evaluateExpr(props.visibilityExpr, props['source'])
        }
        props['value'] = props['source'][sub_props.key] || false;
        return props;
    }
    updateConfigValue (key, value) {
        var rawValue = toRaw(this.updatedValue);
        rawValue[key] = value;
        this.env.updateConfigValue(this.key, rawValue);
    }
    updateSource (key, value) {
        this.props.source[this.key][key] = value;
        this.env.updateSource(this.key, this.props.source[this.key]);
    }
}
ThemeOptionJson.template = 'theme_config.JSON';

export class ThemeOptionBottomBar extends AbstractThemeOption {
    setup() {
        super.setup();
        this.orm = useService("orm");
        this.state = useState({
            'actions': this.props.value
        });
        onWillStart(async () => {
            this.allButtons = await this.orm.call('website', 'get_theme_prime_bottom_bar_action_buttons');
        });
    }
    removeAction (action) {
        const index = this.state.actions.indexOf(action);
        this.state.actions.splice(index, 1);
        this.updateSource(this.state.actions);
    }
    addAction (action) {
        this.state.actions.push(action);
        this.updateSource(this.state.actions);
    }
}
ThemeOptionBottomBar.template = 'theme_config.BottomBar';


export class ThemeConfigDialog extends Component {
    setup() {
        this.orm = useService('orm');
        this.website = useService('website');
        this.title = this.env._t("Theme Configuration");
        this.primaryTitle = this.env._t("Save");
        this.size = 'md';
        this.updatedValue = {};
        this.source = useState({});
        this._coreProps = {
            updateConfigValue: this.updateConfigValue.bind(this),
            updateSource: this.updateSource.bind(this)
        };
        onWillStart(async () => {
            var source = await this.orm.call("website", "get_dr_theme_config", [this.website.currentWebsite.id]);
            for (var key in source) {
                this.source[key] = source[key];
            }
        });
        useCore({});
    }

    async saveConfig() {
        await this.orm.call("dr.theme.config", "save_config", [[], this.website.currentWebsite.id, this.updatedValue]);
        window.location.reload();
    }

    get _tabInfo() {
        return [{
            name: 'general',
            icon: 'fa fa-sliders',
            label: _t('General'),
            components: [
                { props: { title: _t('Search'), subtitle: _t('Tweak search behavior for your website.'), _classes: 'mt-0'}, componentRef: ThemeOptionTitle },
                { props: { key: 'json_product_search', components: [
                    { props: { key: 'advance_search', label: _t('Enable advance search')}, componentRef: ThemeOptionCheckbox },
                    { props: { key: 'search_category', label: _t('Categories'), visibilityExpr: 'advance_search'}, componentRef: ThemeOptionCheckbox },
                    { props: { key: 'search_attribute', label: _t('Smart Autocomplete'), visibilityExpr: 'advance_search'}, componentRef: ThemeOptionCheckbox },
                    { props: { key: 'search_suggestion', label: _t('Smart Suggestion'), visibilityExpr: 'advance_search'}, componentRef: ThemeOptionCheckbox },
                    { props: { key: 'search_fuzzy', label: _t('Fuzzy search'), visibilityExpr: 'advance_search'}, componentRef: ThemeOptionCheckbox },
                    { props: { key: 'search_fill_products', label: _t('Auto products fill'), tooltip: _("When products does not match search term, this option will try to fill associated products."), visibilityExpr: 'advance_search'}, componentRef: ThemeOptionCheckbox },
                    { props: { key: 'search_max_product', label: _t('Products limit'), tooltip: _("Max 5"), visibilityExpr: 'advance_search'}, componentRef: ThemeOptionNumber },
                    { props: { key: 'search_limit', label: _t('Result Limit'), tooltip: _("Min 5 and Max 10"), visibilityExpr: 'advance_search'}, componentRef: ThemeOptionNumber },
                    { props: { key: 'search_report', label: _t('Search Report'), visibilityExpr: 'advance_search'}, componentRef: ThemeOptionCheckbox },
                    { props: { key: 'delete_search_report', label: _t('Auto Delete Search Report'), note: "days", tooltip: _("Keep it at 0 to stop auto delete"), visibilityExpr: 'advance_search'}, componentRef: ThemeOptionNumber },
                ]}, componentRef: ThemeOptionJson},
                { props: { key: 'cart_flow_title', title: _t('Cart Flow'), subtitle: _t('You can change how products are being added in cart.')},  key: 'cart_flow_title', componentRef: ThemeOptionTitle},
                { props: { key: 'cart_flow', selection: [['default', 'Default'], ['notification', 'Notification'], ['dialog', 'Dialog'], ['side_cart', 'Open Cart Sidebar']]}, componentRef: ThemeOptionRadio},
                { props: { key: 'brand_title', title: _t('Brand Page')}, componentRef: ThemeOptionTitle},
                { props: { key: 'json_brands_page', components: [
                    { props: { key: 'disable_brands_grouping', label: _t('Disable grouping of brands')}, componentRef: ThemeOptionCheckbox }
                ]}, componentRef: ThemeOptionJson},
                { props: { key: 'lang_title', title: _t('Language/Pricelist Selector')}, componentRef: ThemeOptionTitle},
                { props: { key: 'json_general_language_pricelist_selector', components: [
                    { props: { key: 'hide_country_flag', label: _t('Hide country flag')}, componentRef: ThemeOptionCheckbox }
                ]}, componentRef: ThemeOptionJson},
                { props: { title: _t('B2b Configuration'), subtitle: _t('Tweak your shop behavior.')}, componentRef: ThemeOptionTitle },
                { props: { key: 'json_b2b_shop_config', components: [{ props: { key: 'dr_enable_b2b', label: _t('B2B Mode'), tooltip: _("This option will hide product price for public users and don't allow them to place an order") }, componentRef: ThemeOptionCheckbox }, { props: { key: 'dr_only_assigned_pricelist', label: _t('Pricelist per customer'), tooltip: _("After enabling this option user will only see assigned pricelist to their contact record.") }, componentRef: ThemeOptionCheckbox }]}, componentRef: ThemeOptionJson},
            ]
        }, {
            name: 'shop',
            icon: 'fa fa-shopping-cart',
            label: _t('Shop'),
            components: [
                { props: { title: _t('Shop'), subtitle: _t('Shop page main layout.'), _classes: 'mt-0' }, componentRef: ThemeOptionTitle },
                { props: { key: 'json_shop_layout', components: [
                    { props: { key: 'layout', label: _t('Layout'), selection: [['prime', 'Prime'], ['default', 'Default']]}, componentRef: ThemeOptionSelection },
                    { props: { key: 'show_view_switcher', label: _t('Show view switcher'), visibilityExpr: "layout == 'prime'"}, componentRef: ThemeOptionCheckbox },
                    { props: { key: 'default_view_mode', label: _t('Default view mode'), selection: [['grid', 'Grid'], ['list', 'List']], visibilityExpr: "layout == 'prime'"}, componentRef: ThemeOptionSelection },
                    { props: { key: 'load_more_products', label: _t('Behavior of load more products'), selection: [['pager', 'Pager'], ['button', 'Load More Button'], ['scroll', 'Infinite Scroll']], visibilityExpr: "layout == 'prime'"}, componentRef: ThemeOptionSelection },
                ], visibilityKey: 'enable'}, componentRef: ThemeOptionJson},
                { props: { title: _t('Category Pills'), subtitle: _t('Show product category pills on top of the shop page.'), visibilityExpr: "json_shop_layout.layout == 'prime'"}, componentRef: ThemeOptionTitle },
                { props: { key: 'json_shop_category_pills', components: [
                    { props: { key: 'active', label: _t('Enable category pills')}, componentRef: ThemeOptionCheckbox },
                    { props: { key: 'style', label: _t('Style'), selection: [['1', 'Card'], ['2', 'Text'], ['3', 'Image + Text'], ['4', 'Image + Text (Rounded)'], ['5', 'Image Only']], visibilityExpr: 'active'}, componentRef: ThemeOptionSelection },
                    { props: { key: 'show_child_categories', label: _t('Show child categories pills of active category'), visibilityExpr: 'active'}, componentRef: ThemeOptionCheckbox },
                    { props: { key: 'hide_in_desktop', label: _t('Hide in desktop device'), visibilityExpr: 'active'}, componentRef: ThemeOptionCheckbox },
                ], visibilityExpr: "json_shop_layout.layout == 'prime'"}, componentRef: ThemeOptionJson},
                { props: { title: _t('Shop Filter'), subtitle: _t('Tweak filters behavior on shop.'), visibilityExpr: "json_shop_layout.layout == 'prime'"}, componentRef: ThemeOptionTitle },
                { props: { key: 'json_shop_filters', components: [
                    { props: { key: 'lazy_method', label: _t('Apply filters with lazy method') }, componentRef: ThemeOptionCheckbox },
                    { props: { key: 'filter_style', label: _t('Filter Style'), selection: [['1', 'Clean'], ['2', 'Underline'], ['3', 'Card'], ['4', 'Bordered'], ['5', 'Boxed']]}, componentRef: ThemeOptionSelection },
                    { props: { key: 'show_in_sidebar', label: _t('Show filters in sidebar')}, componentRef: ThemeOptionCheckbox },
                    { props: { key: 'filter_position', label: _t('Filter Position'), selection: [['left', 'Left'], ['right', 'Right']], visibilityExpr: "show_in_sidebar == false"}, componentRef: ThemeOptionSelection },
                    { props: { key: 'collapsible_category', label: _t('Collapsible category')}, componentRef: ThemeOptionCheckbox },
                    { props: { key: 'collapsible_attribute', label: _t('Collapsible attributes')}, componentRef: ThemeOptionCheckbox },
                    { props: { key: 'show_category_count', label: _t('Show category count')}, componentRef: ThemeOptionCheckbox },
                    { props: { key: 'show_attribute_count', label: _t('Show attribute count') }, componentRef: ThemeOptionCheckbox },
                    { props: { key: 'hide_extra_attrib_value', label: _t('Hide extra attributes'), tooltip: _("Hide attribute value if it is not matched with any product") }, componentRef: ThemeOptionCheckbox },
                    { props: { key: 'show_rating_filter', label: _t('Show rating filter'), tooltip: _("To show rating filter, First you have to activate customers 'Rating' option in product detail page.")}, componentRef: ThemeOptionCheckbox },
                    { props: { key: 'show_availability_filter', label: _t('Show availability filter'), tooltip: _("If you have large number of products this option may affect performance.")}, componentRef: ThemeOptionCheckbox },
                ], visibilityExpr: "json_shop_layout.layout == 'prime'"}, componentRef: ThemeOptionJson},
                { props: { title: _t('Product Card'), subtitle: _t('Configure actions and style of product card.'), visibilityExpr: "json_shop_layout.layout == 'prime'"}, componentRef: ThemeOptionTitle },
                { props: { key: 'json_shop_product_item', components: [
                    { props: { key: 'style', label: _t('Style'), selection: [['1', 'Square'], ['2', 'Rounded']]}, componentRef: ThemeOptionSelection },
                    { props: { key: 'image_size', label: _t('Image Size'), selection: [['default', 'Default (1/1)'], ['landscape', 'Landscape (4/3)'], ['portrait', 'Portrait (4/5)'], ['vertical', 'Vertical (2/3)']]}, componentRef: ThemeOptionSelection },
                    { props: { key: 'image_fill', label: _t('Image Fill'), selection: [['contain', 'Contain'], ['cover', 'Cover'], ['fill', 'Fill']]}, componentRef: ThemeOptionSelection },
                    { props: { title: _t('Product Card Actions'), subtitle: _t('Configure action buttons of product card in shop page.')}, componentRef: ThemeOptionTitle },
                    { props: { key: 'show_add_to_cart', icon: 'fa fa-shopping-cart', label: _t('Show add to cart')}, componentRef: ThemeOptionCardBtnCheckbox },
                    { props: { key: 'show_wishlist', icon: 'fa fa-heart', label: _t('Show wishlist')}, componentRef: ThemeOptionCardBtnCheckbox },
                    { props: { key: 'show_compare', icon: 'fa fa-retweet', label: _t('Show compare')}, componentRef: ThemeOptionCardBtnCheckbox },
                    { props: { key: 'show_quick_view', icon: 'fa fa-eye', label: _t('Show quick view')}, componentRef: ThemeOptionCardBtnCheckbox },
                    { props: { key: 'show_similar_products', icon: 'fa fa-clone', label: _t('Show similar products')}, componentRef: ThemeOptionCardBtnCheckbox },
                    { props: { key: 'show_product_preview_swatches', icon: 'fa fa-adjust', label: _t('Show product preview swatches')}, componentRef: ThemeOptionCardBtnCheckbox },
                    { props: { key: 'show_rating', icon: 'fa fa-star', label: _t('Show rating'), tooltip: _("To show rating, First you have to activate customers 'Rating' option in product detail page.")}, componentRef: ThemeOptionCardBtnCheckbox },
                    { props: { key: 'show_stock_label', icon: 'fa fa-tag', label: _t('Show stock label')}, componentRef: ThemeOptionCardBtnCheckbox },
                ], visibilityExpr: "json_shop_layout.layout == 'prime'"}, componentRef: ThemeOptionJson},
            ]
        }, {
            name: 'product_detail',
            icon: 'fa fa-cube',
            label: _t('Product Detail'),
            components: [
                { props: { title: _t('Zoom Product Images'), subtitle: _t('Zoom product images in product detail page and quick view.'), _classes: 'mt-0' }, componentRef: ThemeOptionTitle },
                { props: { key: 'json_zoom', components: [
                    { props: { key: 'zoom_enabled', label: _t('Enable zoom')}, componentRef: ThemeOptionCheckbox },
                    { props: { key: 'zoom_factor', label: _t('Zoom factor'), visibilityExpr: 'zoom_enabled'}, componentRef: ThemeOptionNumber },
                ], visibilityKey: 'zoom_enabled'}, componentRef: ThemeOptionJson},
                { props: { title: _t('Sticky Add to Cart'), subtitle: _t("Allows users to follow up product's Add to Cart button until bottom scroll reached."), }, componentRef: ThemeOptionTitle },
                { props: { key: 'bool_sticky_add_to_cart', 'label': _t('Enable sticky add to cart') }, componentRef: ThemeOptionCheckbox},
                { props: { title: _t('Product Offers'), subtitle: _t("You will be able to add offers on product and show details in dialog.")}, componentRef: ThemeOptionTitle },
                { props: { key: 'bool_product_offers', 'label': _t('Enable product offers') }, componentRef: ThemeOptionCheckbox},
                { props: { title: _t('General')}, componentRef: ThemeOptionTitle },
                { props: { key: 'bool_show_products_nav', 'label': _t('Product Navigation'), tooltip: _t("Shows button to see next, previous products based on product sequence.") }, componentRef: ThemeOptionCheckbox},
            ]
        }, {
            name: 'mobile',
            icon: 'fa fa-mobile',
            label: _t('Mobile'),
            components: [
                { props: { title: _t('Sidebar'), subtitle: _t('You can change behaviour of sidebars.'), _classes: 'mt-0' }, componentRef: ThemeOptionTitle },
                { props: { key: 'json_sidebar_config', components: [
                    { props: { key: 'category_sidebar_style', label: _t('Category sidebar style'), selection: [['1', 'Text'], ['2', 'Image + Text'], ['3', 'Cover']]}, componentRef: ThemeOptionSelection },
                    { props: { key: 'category_sidebar_show_count', label: _t('Show product count in category sidebar') }, componentRef: ThemeOptionCheckbox },
                    { props: { key: 'menu_sidebar_show_category', label: _t('Show category link in menu sidebar') }, componentRef: ThemeOptionCheckbox },
                    { props: { key: 'cart_sidebar_free_delivery_progress', label: _t('Show free delivery progress in cart sidebar') }, componentRef: ThemeOptionCheckbox },
                ]}, componentRef: ThemeOptionJson},
                { props: { title: _t('Bottombar'), subtitle: _t("Bottom bar allow movement between primary destinations on the website.")}, componentRef: ThemeOptionTitle },
                { props: { key: 'json_bottom_bar', components: [
                    { props: { key: 'show_bottom_bar', label: _t('Show Bottombar')}, componentRef: ThemeOptionCheckbox },
                    { props: { key: 'show_bottom_bar_on_scroll', label: _t('Show Bottombar On Scroll'), visibilityExpr: 'show_bottom_bar'}, componentRef: ThemeOptionCheckbox },
                    { props: { key: 'filters', label: _t('Show sort and filter button on shop'), visibilityExpr: 'show_bottom_bar'}, componentRef: ThemeOptionCheckbox },
                    { props: { key: 'actions', label: _t('Buttombar Buttons'), visibilityExpr: 'show_bottom_bar'}, componentRef: ThemeOptionBottomBar },
                ], visibilityKey: 'show_bottom_bar'}, componentRef: ThemeOptionJson},
            ]
        }
    ];}
    prepareProps (props) {
        props = props || {};
        props['source'] = this.source;
        props['visibility'] = true;
        if (props.key) {
            props['value'] = this.source[props.key] || false;
        }
        if (props.visibilityExpr) {
            props['visibility'] = evaluateExpr(props.visibilityExpr, this.source)
        }
        return props;
    }

    updateConfigValue (key, value) {
        this.updatedValue[key] = value;
    }
    updateSource (key, value) {
        this.source[key] = value;
    }
}

ThemeConfigDialog.template = 'droggol_theme_common.ThemeConfigDialog';
ThemeConfigDialog.components = { WebsiteDialog };
