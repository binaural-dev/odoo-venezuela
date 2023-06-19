/** @odoo-module */
import { registry } from "@web/core/registry";
import { AbstractComponent } from './abstract_component';


export class TpUiComponent extends AbstractComponent {
    setup() {
        let { cardRegistry, defaultVal, noSelection, forceVisible } = this.props.extras;
        this.supportedComponents = Object.keys(defaultVal);
        this.stylesRegistry = cardRegistry ? registry.category(cardRegistry) : false;
        this.noSelection = noSelection || false;
        this.forceVisible = forceVisible || false;
        this._coreProps = {
            changeValue: this._onChangeComponentValue.bind(this),
        };
        super.setup();
    }
    _onChangeComponentValue (value ,name) {
        this.env.updateUiComponentValue(name, value);
        // Ugly hack we should avoid it let's do the magic someday
        if (name === 'style' && this.stylesRegistry) {
            let config = this.stylesRegistry.get(value);
            if ('supportedActions' in config) {
                this.env.updateUiComponentValue('activeActions', [... this.actionProps.supportedActions]);
            }
        }
    }
    get componentRegistry() {
        return {
            TpDropDown: ['style', 'mode', 'header', 'productListing', 'childOrder', 'tabStyle', 'sortBy', 'mobileStyle', 'mobileMode'],
            TpRangeInput: ['ppr', 'limit'],
            TpBoolean: ['includesChild', 'bestseller', 'newArrived', 'discount', 'menuLabel'],
            TpActions: ['activeActions'],
            TpCardGrid: ['categoryTabsConfig'],
            TpComponentGroup: ['mobileConfig'],
        }
    }
    get headers() {
        let headerRegistry = registry.category('theme_prime_product_list_cards_headers');
        return Object.keys(headerRegistry.content);
    }
    get styles() {
        return Object.keys(this.stylesRegistry.content);
    }
    get nodeOptions() {
        let buttonClasses = { buttonClasses: "btn d-flex justify-content-between align-items-center btn-default bg-white border shadow-sm fw-light w-100"};
        return { mobileConfig: { title: this.env._t("Mobile Settings") }, style: {...buttonClasses, title: this.env._t("Style"), records: _.map(this.styles, (style, index) => { return { id: style, title: this.env._t(`Style - ${index + 1}`) }; })}, mode: {...buttonClasses, title: this.env._t("Mode"), records: [{ id: 'grid', iconClass: 'fa fa-th-large pe-2', title: this.env._t('Grid') }, { iconClass: 'fa pe-2 fa-arrows-h', id: 'slider', title: this.env._t('Slider') }]}, header: {...buttonClasses, title: this.env._t("Header Style"), records: _.map(this.headers, (header, index) => { return { id: header, title: this.env._t(`Style - ${index + 1}`) }; })}, productListing: {...buttonClasses, title: this.env._t("Product Listing"), records: [{ iconClass: 'fa fa-percent', id: 'discount', title: this.env._t("On Sale") }, { iconClass: 'fa fa-clock-o', id: 'newArrived', title: this.env._t("Newly Arrived") }, { id: 'bestseller', iconClass: 'dri dri-bolt', title: this.env._t("Bestseller") }]}, childOrder: {...buttonClasses, title: this.env._t("Child Order"), records: [{ id: 'count', title: this.env._t("No. of Products") }, { id: 'sequence', title: this.env._t("Sequence") }]}, tabStyle: {...buttonClasses, title: this.env._t("Tab Style"), records: _.map([1, 2, 3, 4, 5, 6], (style, index) => { return { id: `tp-droggol-dynamic-snippet-tab-${index + 1}`, title: this.env._t(`Style - ${index + 1}`) }; })}, sortBy: {...buttonClasses, title: this.env._t("Sort by"), records: [{ id: 'list_price asc', iconClass: 'fa fa-sort-numeric-asc', title: this.env._t("Price: Low to High") }, { id: 'list_price desc', iconClass: 'fa fa-sort-numeric-desc', title: this.env._t("Price: High to Low") }, { id: 'name asc', iconClass: 'fa fa-sort-alpha-asc', title: this.env._t("Name: A to Z") }, { id: 'name desc', iconClass: 'fa fa-sort-alpha-desc', title: this.env._t("Name: Z to A") }, { iconClass: 'fa fa-clock-o', id: 'create_date desc', title: this.env._t("Newly Arrived") }, { id: 'bestseller', iconClass: 'dri dri-bolt', title: this.env._t("Bestseller") }]}, limit: { title: this.env._t("No. of items"), maxValue: 20, minValue: 0 }, ppr: { title: this.env._t('Product Per Row')}, includesChild: { title: this.env._t('add Products From Child Categories')}, bestseller: { title: this.env._t('Bestseller')}, newArrived: { title: this.env._t('Newly Arrived')}, menuLabel: { title: this.env._t('Display label')}, discount: { title: this.env._t('On Sale')}, activeActions: this.actionProps, categoryTabsConfig: {}}
    }
    get componentDefaultVal() {
        return this.props.componentData;
    }
    get activeActions() {
        let item = this.stylesRegistry.get(this.componentDefaultVal.style);
        if (item.supportedActions) {
            return this.props.componentData.activeActions || [... this.stylesRegistry.get(this.componentDefaultVal.style).supportedActions];
        }
        return [];
    }
    get actionProps() {
        return {
            supportedActions: [... this.stylesRegistry.get(this.componentDefaultVal.style).supportedActions],
            activeActions: this.activeActions,
        }
    }
}
TpUiComponent.template = 'theme_prime.TpUiComponent';