/** @odoo-module */
import { useService } from '@web/core/utils/hooks';
import { MediaDialog } from '@web_editor/components/media_dialog/media_dialog';
const { Component, onWillStart, onWillUpdateProps, toRaw, useState, useRef } = owl;
import { debounce } from '@web/core/utils/timing';
import { registry } from '@web/core/registry';
import { AbstractComponent, CoreComponent } from './abstract_component';

/************************************************************
        *                                                           *
        *  .=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-.       *
        *   |                     ______                     |      *
        *   |                  .-"      "-.                  |      *
        *   |                 /            \                 |      *
        *   |     _          |              |          _     |      *
        *   |    ( \         |,  .-.  .-.  ,|         / )    |      *
        *   |     > "=._     | )(__/  \__)( |     _.=" <     |      *
        *   |    (_/"=._"=._ |/     /\     \| _.="_.="\_)    |      *
        *   |           "=._"(_     ^^     _)"_.="           |      *
        *   |               "=\__|IIIIII|__/="               |      *
        *   |              _.="| \IIIIII/ |"=._              |      *
        *   |    _     _.="_.="\          /"=._"=._     _    |      *
        *   |   ( \_.="_.="     `--------`     "=._"=._/ )   |      *
        *   |    > _.="                            "=._ <    |      *
        *   |   (_/                                    \_)   |      *
        *   |                                                |      *
        *   '-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-='      *
        *                                                           *
        *   If this comment is removed the program will blow up     *
        *************************************************************/

export class TpDropDown extends Component {
    setup() {
        let { buttonClasses, name, title } = this.props;
        this.name = name;
        this.title = title;
        this.buttonClasses = buttonClasses || 'btn-primary';
        super.setup();
    }
    _getRecordByID(recordID) {
        return this.props.records.find((record) => record.id === recordID);
    }
    _onClickItem(recordID) {
        this.env.changeValue(recordID, this.name);
    }
}
TpDropDown.template = 'theme_prime.TpDropDown';

export class TpSearchInput extends CoreComponent {
    setup() {
        let { defaultParams, fieldsToMarkup } = this.props;
        this.defaultParams = defaultParams;
        this.fieldsToMarkup = fieldsToMarkup;
        this.model = this.defaultParams.model;
        this.search = debounce((ev) => this._onSearch(ev), 400);
        this.onFocusout = debounce((ev) => this._onFocusout(ev), 200);
        // useRef is not a good idea. We will find another way someday :)
        this.searchInput = useRef('tp-search-input');
        this.searchComponent = useRef('tp-search-component');
        this.searchDropdown = useRef('tp-search-dropdown');

        this.componentService = useService('shared_component_service');
        this.state = useState({records: [], term: ''});
        super.setup();
    }
    async _onSearch (event) {
        let term = event.target.value;
        let extras = {'brands' : this.defaultParams.model === "product.attribute.value" && this.props.brand ? this.props.brand : false};
        if (term) {
            let params = { ...this.defaultParams, domain: this._getSearchDomain(term), extras: extras, limit:5 };
            this.state.records = await this.componentService._fetchRecords(params, { fieldsToMarkup: this.fieldsToMarkup });
        } else {
            this._clearAutoComplete();
        }
        this.state.term = term;
    }
    _onFocusout () {
        if (!this.searchComponent.el.contains(document.activeElement)) {
            this._clearAutoComplete();
        }
    }
    _onClickSelectRecord (recordID) {
        this.env.performAction('ADD', recordID);
        this._clearAutoComplete();
    }
    _getSearchDomain (term) {
        if (term) {
            return [['id', 'not in', this.getExcludedRecordsIDs], ['name', 'ilike', term]];
        }
        return [['id', 'not in', this.getExcludedRecordsIDs]];
    }
    _clearAutoComplete () {
        this.searchInput.el.value = '';
        this.state.term = '';
    }
    get getExcludedRecordsIDs () {
        return this.props.recordsIDs || [];
    }
    get resModelInfo() {
        return {
        'product.template': { title: this.env._t("Products"), template: 'theme_prime.tpProductPlaceHolder'},
        'product.public.category': { title: this.env._t("Categories"), template: 'theme_prime.tpProductPlaceHolder'},
        'product.attribute.value': { title: this.props.brand ? this.env._t("Brand")  : this.env._t("Attribute")},
        'dr.product.label': { title: this.env._t("Label")},
        'product.tag': { title: this.env._t("Tags")}};
    }
}
TpSearchInput.template = 'theme_prime.TpSearchInput';


export class TpRangeInput extends Component {
    setup() {
        this.maxValue = this.props.maxValue || 6;
        this.minValue = 'minValue' in this.props ? this.props.minValue : 4;
        this.title = this.props.title;
        this.input = useRef('tp-range-input');
    }
    onChangeInput(ev) {
        this.env.changeValue(parseInt(ev.currentTarget.value), this.props.name);
    }
    onInput(ev) {
        let percentage = (parseInt(ev.currentTarget.value) - this.minValue) / (this.maxValue - this.minValue) * 100;
        this.input.el.style.backgroundImage = `linear-gradient(90deg, #0080ff ${percentage}%, transparent ${percentage}%)`;
    }
    get value() {
        return 'value' in this.props ? parseInt(this.props.value) : 4;
    }
    get style() {
        let percentage = (this.value - this.minValue) / (this.maxValue - this.minValue) * 100;
        return `linear-gradient(90deg, #0080ff ${percentage}%, transparent ${percentage}%)`
    }
}
TpRangeInput.template = 'theme_prime.TpRangeInput';

export class TpBoolean extends Component {
    setup() {
        this.title = this.props.title;
        this.switch = this.props.switch || false;
        this.name = name;
        this.uid = _.uniqueId('tp-boolean-component-');
    }
    onChangeInput(ev) {
        this.env.changeValue(ev.currentTarget.checked, this.props.name);
    }
    get value() {
        return _.contains(_.keys(this.props), 'value') ? this.props.value : false;
    }
}
TpBoolean.template = 'theme_prime.TpBoolean';

export class TpImageUpload extends Component {
    setup() {
        this.dialogs = useService('dialog');
        this.title = this.props.title;
    }
    onClick(ev) {
        this.dialogs.add(MediaDialog, {
            onlyImages: true,
            resModel: 'ir.ui.view',
            useMediaLibrary: true,
            save: image => {
                this.env.changeValue(image.src, this.props.name);
            },
        });
    }
    onClickRemove() {
        this.env.changeValue(false, this.props.name);
    }
    get value() {
        return _.contains(_.keys(this.props), 'value') ? this.props.value : false;
    }
}
TpImageUpload.template = 'theme_prime.TpImageUpload';

export class TpCardGrid extends AbstractComponent {
    setup() {
        let { value } = this.props;
        this._coreCProps = {
            changeValue: this._onChangeComponentValue.bind(this),
        };
        this.state = useState({
            value: toRaw(value.activeRecordID),
            records: toRaw(this.recordsIDs),
            activeConfig: this.getRecordFromData(value.records, value.activeRecordID)
        });
        super.setup();
        onWillUpdateProps(this._insertFromProps);
        onWillStart(async () => {
            await this.updateData()
        });
    }
    get supportedComponents() {
        return ['style', 'productListing', 'child', 'limit', 'brand', 'label', 'count', 'background'];
    }
    get componentRegistry() {
        return {TpDropDown: ['style', 'productListing'], TpRangeInput: ['child', 'limit'], TpBoolean: ['brand', 'label', 'count'], TpImageUpload: ['background']};
    }
    get componentDefaultVal() {
        return this.state.activeConfig;
    }
    get nodeOptions() {
        let buttonClasses = { buttonClasses: "btn d-flex justify-content-between align-items-center btn-default bg-white border shadow-sm fw-light w-100" };
        return {style: { ...buttonClasses, title: this.env._t("Style"), records: _.map(this.styles, (style, index) => { return { id: style, title: this.env._t(`Style - ${index + 1}`) }; }) }, productListing: { ...buttonClasses, title: this.env._t("Product Listing"), records: [{ id: 'bestseller', title: this.env._t("Best Seller"), iconTemplate: 'dri dri-bolt' }, { iconTemplate: 'fa fa-percent', id: 'discount', title: this.env._t("Discount") }]}, limit: { title: this.env._t("No. of items"), maxValue: 20, minValue: 4 }, child: { title: this.env._t("No. of Child"), maxValue: 20, minValue: 3 }, brand: { title: this.env._t("Brands")}, label: { title: this.env._t("Label")}, count: { title: this.env._t("Count")}, background: { title: this.env._t("Bg. Image")}};
    }
    async updateData(IDs) {
        let recordsIDs = IDs || this.recordsIDs;
        let fetchedCategoryData = await this.componentService._fetchRecords({ options: { getCount: true, categoryIDs: recordsIDs }, fields: ['dr_category_label_id'] }, { routePath: '/theme_prime/get_categories_info' });
        let records = [];
        recordsIDs.forEach((resID) => {
            let matchedRecord = this.getRecordFromData(fetchedCategoryData, resID);
            if (matchedRecord) {
                records.push({ title: matchedRecord.name, id: resID, imgSrc: `/web/image/product.public.category/${resID}/image_128`, subtitle: `${matchedRecord.count} Products` })
            }
        });
        this.state.value = records.length ? this.props.value.activeRecordID : false;
        this.state.records = records;
        this.state.activeConfig = this.getRecordFromData(this.props.value.records, this.state.value);;
    }
    getRecordFromData(records, recordID) {
        return records.find((record) => record.id === recordID);
    }
    async _insertFromProps(nextProps) {
        this.updateData(nextProps.value.records.map(rec => rec.id));
    }
    get getCardComponent() {
        return TpCardComponent;
    }
    get recordsIDs() {
        return this.props.value.records.map(rec => rec.id);
    }
    getValues(recordID) {
        return this.props.value.records.find((record) => record.id === recordID);
    }
    get styles() {
        return Object.keys(registry.category('theme_prime_mega_menu_cards').content);
    }
    _onChangeComponentValue(value, name) {
        if (name === 'categories') {
            this.state.activeConfig = this.getRecordFromData(this.props.value.records, value);
            this.state.value = value;
            this.env.changeValue({ activeRecordID: value, records: toRaw(this.props.value.records) }, 'categoryTabsConfig');
        } else {
            let rec = this.getValues(this.state.value);
            rec[name] = value;
            this.env.changeValue({ activeRecordID: this.state.value, records: toRaw(this.props.value.records) }, 'categoryTabsConfig');
        }
    }
}
TpCardGrid.template = 'theme_prime.TpCardGrid';
TpCardGrid.components = { TpDropDown };

export class TpComponentGroup extends AbstractComponent {
    setup() {
        let { value } = this.props;
        this.value = value;
        this.supportedComponents = Object.keys(this.value);
        this._coreCProps ={
            changeValue: this._onChangeComponentValue.bind(this),
        };
        super.setup();
    }
    get mobileStyles() {
        let headerRegistry = registry.category('theme_prime_mobile_card_registry');
        return Object.keys(headerRegistry.content);
    }
    get componentRegistry() {
        return {
            TpDropDown: ['style', 'mode'],
        }
    }
    get nodeOptions () {
        let buttonClasses = { buttonClasses: "btn d-flex justify-content-between align-items-center btn-default bg-white border shadow-sm fw-light w-100" };
        return {
            style: { ...buttonClasses, title: this.env._t("Mobile Style"), records: _.union([{ id: 'default', title: this.env._t('Same as Desktop') }], _.map(this.mobileStyles, (style, index) => { return { id: style, title: this.env._t(`Style - ${index + 1}`) }; })) },
            mode: { ...buttonClasses, title: this.env._t("Mode"), records: [{ id: 'default', title: this.env._t('Same as Desktop') }, { id: 'grid', iconTemplate: 'fa fa-th-large pe-2', title: this.env._t('Grid') }, { iconTemplate: 'fa pe-2 fa-arrows-h', id: 'slider', title: this.env._t('Slider') }] },
        };
    }
    get componentDefaultVal() {
        return this.value;
    }
    _onChangeComponentValue(value, name) {
        this.value[name] = value;
        this.env.changeValue(toRaw(this.value), this.props.name);
    }
}
TpComponentGroup.template = 'theme_prime.TpComponentGroup';

export class TpActions extends Component {
    setup() {
        this.orm = useService("orm");
        this.website = useService('website');
        onWillStart(async () => {
            this.shopConfig = await this.orm.call("website", "get_theme_prime_shop_config", [], { context: { website_id: this.website.currentWebsite.id } });
        });
    }
    get supportedActions() {
        return [...this.props.supportedActions];
    }
    get activeActions() {
        return [...this.props.activeActions] || [];
    }
    _getAction(action) {
        let allActions = { colors: { icon: 'theme_prime.icon_brush', label: this.env._t('Colors') }, count: { icon: 'theme_prime.icon_hash_tag', label: this.env._t("Count") }, brand: { icon: 'theme_prime.icon_tag', label: this.env._t("Brands") }, quick_view: { icon: 'theme_prime.icon_eye', label: this.env._t('QUICK VIEW') }, add_to_cart: { icon: 'theme_prime.icon_cart', label: this.env._t('ADD TO CART') }, category_info: { icon: 'theme_prime.icon_font', label: this.env._t('CATEGORY') }, wishlist: { icon: 'theme_prime.icon_heart', label: this.env._t('WISHLIST') }, comparison: { icon: 'theme_prime.icon_exchange', label: this.env._t('COMPARE') }, rating: { icon: 'theme_prime.icon_star', label: this.env._t('RATING') }, description_sale: { icon: 'theme_prime.icon_description', label: this.env._t('DESCRIPTION') }, label: { icon: 'theme_prime.icon_tag', label: this.env._t('LABEL') }, show_similar: { icon: 'theme_prime.icon_box', label: this.env._t('SIMILAR') } };
        let selectedAction = _.contains(_.keys(allActions), action) ? allActions[action] : false;
        if (_.contains(['rating', 'wishlist', 'comparison'], action) && !this.shopConfig[`is_${action}_active`]) {
            selectedAction['disabled'] = true;
            selectedAction['title'] = `${action} is disabled from the shop if you want to use it please enable it from the shop`;
        }
        return selectedAction;
    }
    onActionClick(action) {
        let actions = this.activeActions;
        if (actions.includes(action)) {
            actions.splice(actions.indexOf(action), 1);
        } else {
            actions.push(action)
        }
        this.env.changeValue(actions, 'activeActions');
    }
}
TpActions.template = 'theme_prime.TpActions';

export class TpDomainComponent extends AbstractComponent {
    setup() {
        this.value = {...this.props};
        this.supportedComponents = ['limit', 'order'];
        this.state = useState({
            domainProps: this.prepareDomainValues(this.value.domain),
            condition: this.value.domain.length && this.value.domain[0] === '|' ? 'or' : 'and'
        });
        this._coreProps = {
            changeValue: this._onChangeComponentValue.bind(this),
        };
        this._coreCProps = {
            updateSelectionComponentValue: this.updateSelectionComponentValue.bind(this),
            recordsReady: this.onRecordsReady.bind(this)
        };
        super.setup();
    }
    prepareDomainValues(domain) {
        domain = this._normalizeDomain(toRaw(domain))
        let values = [];
        domain.forEach((collection) => {
            values.push({
                domain: collection,
                editMode: false,
                records: [],
            });
        });
        return values;
    }
    onRecordsReady(records, key) {
        if (this.state.domainProps[key].records.length !== records.length) {
            this.state.domainProps[key].records = toRaw(records);
        }
    }
    async updateSelectionComponentValue(key, value, name) {
        if (key === 'recordsIDs') {
            this.state.domainProps[name].domain[2] = value;
        }
    }
    _onChangeCondition(ev) {
        this.state.condition = ev.currentTarget.value;
        this._onChangeComponentValue(toRaw(this.domainToCondition), 'domain');
    }
    _onChangeComponentValue(value, name) {
        if (name === 'domainTemplate') {
            let { domain, sortBy } = this.getRecord(this.domainTemplates, value);
            this.state.domainProps = this.prepareDomainValues(this._normalizeDomain(domain))
            if (sortBy) {
                this._onChangeComponentValue(sortBy, 'order')
            }
        } else {
            this.value[name] = value;
            this.env.performAction('ADVANCE', this.value)
        }
    }
    _normalizeDomain(domain) {
        return domain.filter((node) => { return Array.isArray(node)})
    }
    onAddNewRule() {
        let { domainProps } = this.state;
        domainProps.push({domain: ['name', 'ilike', ''], editMode: true, records: []});
        this.state['domainProps'] = domainProps;
    }
    onChangeValue(ev, index, fieldType) {
        let value = fieldType === 'integer' ? parseInt(ev.target.value) : ev.target.value;
        this.state.domainProps[index].domain[2] = value;
    }
    onEditRule(index, mode) {
        this.state.domainProps.forEach((val, i) => {
            if (index === i) {
                val.editMode = mode;
            }
        });
        if (!mode) {
            this._onChangeComponentValue(toRaw(this.domainToCondition), 'domain');
        }
    }
    onDeleteRule(index) {
        this.state.domainProps.splice(index, 1);
        this._onChangeComponentValue(toRaw(this.domainToCondition), 'domain');
    }
    get fieldsList () {
        return [{'type': 'text', 'name': 'name', 'label': this.env._t('Name') }, {'type': 'many2many', 'name': 'public_categ_ids', 'label': this.env._t('Category'), 'relationModel': 'product.public.category' }, {'type': 'many2one', 'name': 'dr_brand_value_id', 'label': this.env._t('Brand'), 'relationModel': 'product.attribute.value', 'extras': { 'brands': true } }, {'type': 'many2one', 'name': 'attribute_line_ids.value_ids', 'label': this.env._t('Attributes'), 'relationModel': 'product.attribute.value' }, {'type': 'many2one', 'name': 'dr_label_id', 'label': this.env._t('Label'), 'relationModel': 'dr.product.label' }, {'type': 'integer', 'name': 'list_price', 'label': this.env._t('Price') }, {'type': 'many2one', 'name': 'product_tag_ids', 'label': this.env._t('Tags'), 'relationModel': 'product.tag', 'is_multi_website': true }, {'type': 'boolean', 'name': 'dr_has_discount', 'label': this.env._t('Discount') }];
    }
    get domainTemplates() {
        return [{ id: 0, subtitle: this.env._t("Select any template and modify as per your need.") , title: this.env._t("Choose Template"), domain: [], sortBy: 'create_date desc' },{ id: 1, subtitle: this.env._t("Show newly arrived products based on creation date") , title: this.env._t("New Arrival"), domain: [], sortBy: 'create_date desc' },{ id: 2, subtitle: this.env._t("Show newly arrived products from selected categories"),title: this.env._t("Category New Arrival"), domain: [["public_categ_ids", "in", []]], sortBy: 'create_date desc' },{ id: 3, subtitle: this.env._t("Show newly arrived products from selected brands"), title: this.env._t("Brand New Arrival"), domain: [["dr_brand_value_id", "in", []]], sortBy: 'create_date desc' },{ id: 4, subtitle: this.env._t("Show newly arrived products from selected tags"), title: this.env._t("Tags New Arrival"), domain: [["product_tag_ids", "in", []]], sortBy: 'create_date desc' },{ id: 5, subtitle: this.env._t("Show newly arrived products from selected label."), title: this.env._t("Label New Arrival"), domain: [["dr_label_id", "in", []]], sortBy: 'create_date desc' },{ id: 6, subtitle: this.env._t("Show discounted products based on product pricelist"), title: this.env._t("Discounted Products"), domain: [['dr_has_discount', '!=', false]], sortBy: 'list_price asc' },{ id: 7, subtitle: this.env._t("Show discounted products based on product pricelist from selected categories"), title: this.env._t("Category Discounted Products"), domain: ['&', ['dr_has_discount', '!=', false], ["public_categ_ids", "in", []]], sortBy: 'list_price asc' },{ id: 8, subtitle: this.env._t("Show discounted products based on product pricelist from selected brands."), title: this.env._t("Brand Discounted Products"), domain: ['&', ['dr_has_discount', '!=', false], ["dr_brand_value_id", "in", []]], sortBy: 'list_price asc' },{ id: 9, subtitle: this.env._t("Show discounted products based on product pricelist from selected tags"), title: this.env._t("Tags Discounted Products"), domain: ['&', ['dr_has_discount', '!=', false], ["product_tag_ids", "in", []]], sortBy: 'list_price asc' },{ id: 10, subtitle: this.env._t("Show discounted products based on product pricelist from selected label"), title: this.env._t("Label Discounted Products"), domain: ['&', ['dr_has_discount', '!=', false], ["dr_label_id", "in", []]], sortBy: 'list_price asc' },{ id: 11, subtitle: this.env._t("Show best seller products based on last 30 days sales"), title: this.env._t("Best Seller"), domain: [], sortBy: 'bestseller' },{ id: 12, subtitle: this.env._t("Show best seller products based on last 30 days sales from selected categories."), title: this.env._t("Category Best Seller"), domain: [["public_categ_ids", "in", []]], sortBy: 'bestseller' },{ id: 13, subtitle: this.env._t("Show best seller products based on last 30 days sales from selected brands."), title: this.env._t("Brand Best Seller"), domain: [["dr_brand_value_id", "in", []]], sortBy: 'bestseller' },{ id: 14, subtitle: this.env._t("Show best seller products based on last 30 days sales from selected tags."), title: this.env._t("Tags Best Seller"), domain: [["product_tag_ids", "in", []]], sortBy: 'bestseller' },{ id: 15, subtitle: this.env._t("Show best seller products based on last 30 days sales from selected label."), title: this.env._t("Label Best Seller"), domain: [["dr_label_id", "in", []]], sortBy: 'bestseller' },{ id: 16, subtitle: this.env._t("Show best seller products with discount"), title: this.env._t("Discounted Best Seller"), domain: [['dr_has_discount', '!=', false]], sortBy: 'bestseller' },{ id: 17, subtitle: this.env._t("Show best seller products with discount from the selected categories"), title: this.env._t("Category Discounted Best Seller"), domain: ['&', ["public_categ_ids", "in", []], ['dr_has_discount', '!=', false]], sortBy: 'bestseller' },{ id: 18, subtitle: this.env._t("Show best seller products with discount from the selected brands"), title: this.env._t("Brand Discounted Best Seller"), domain: ['&', ["dr_brand_value_id", "in", []], ['dr_has_discount', '!=', false]], sortBy: 'bestseller' },{ id: 19, subtitle: this.env._t("Show best seller products with discount from the selected tags"), title: this.env._t("Tags Discounted Best Seller"), domain: ['&', ["product_tag_ids", "in", []], ['dr_has_discount', '!=', false]], sortBy: 'bestseller' },{ id: 20, subtitle: this.env._t("Show best seller products with discount from the selected label"), title: this.env._t("Label Discounted Best Seller"), domain: ['&', ["dr_label_id", "in", []], ['dr_has_discount', '!=', false]], sortBy: 'bestseller' }];
    }
    _prepareRecords(index) {
        let { domain } = this.state.domainProps[index];
        let field = domain[0];
        return {
            componentData: { selectionType: 'manual', recordsIDs: domain[2]},
            name: index,
            extras: { fields: ['name'], model: this.getRecord(this.fieldsList, field, 'name').relationModel, mode: 'badge', isBrand: this.getRecord(this.fieldsList, field, 'name').relationModel === 'product.attribute.value' && field === 'dr_brand_value_id' ? true : false }
        }
    }
    getRelatedOperator(field) {
        let fieldsInfo = this.fieldsList.find((record) => record.name === field);
        return this.operatorInfo[fieldsInfo.type].value;
    }
    onChangeField (ev, index) {
        let fieldName = ev.target.value;
        let fieldType = this.getRecord(this.fieldsList, fieldName, 'name').type;
        let op = Object.keys(this.getRelatedOperator(fieldName))[0];
        this.state.domainProps[index] ={domain: [fieldName, op, this.operatorInfo[fieldType].defaultVal], editMode: true, records: []};
    }
    onChangeOperator (ev, index) {
        let {domain, records} = this.state.domainProps[index];
        this.state.domainProps[index] = { domain: [domain[0], ev.target.value, domain[2]], editMode: true, records: records};
    }
    get domainToCondition() {
        let sign = this.state.condition === 'and' ? '&' : '|';
        let { domainProps } = this.state;
        let domain = Array.from({ length: domainProps.length - 1 }, (x, i) => sign);
        domainProps.forEach((item) => {
            domain.push(item.domain);
        });
        return domain;
    }
    get operatorInfo () {
        return {'text': {value: { 'ilike': "contains", 'not ilike': "doesn't contain", '=': "is equal to", '!=': "is not equal to" }, defaultVal: ''},'many2many': {value: { 'in': "is having", 'not in': "is not having", 'child_of': "is having child" }, defaultVal: []},'many2one':{value: { 'in': "is having", 'not in': "is not having" }, defaultVal: []},'integer': {value: { '=': "equals to", '!=': "not equals to", '>': 'greater than', '<': 'less then' }, defaultVal: 100},'boolean': {value: { '!=': 'having', '=': 'not having' }, defaultVal: false }};
    }
    get componentRegistry() {
        return {TpDropDown: ['order'], TpRangeInput: ['limit']}
    }
    get nodeOptions() {
        return { limit: { title: this.env._t("No. of items"), maxValue: 20, minValue: 4 }, order: { buttonClasses: "btn d-flex btn-sm justify-content-between align-items-center btn-default bg-white border shadow-sm fw-light w-100", title: this.env._t("Order By"), records: [{ id: 'list_price asc', title: this.env._t("Price: Low to High") }, { id: 'list_price desc', title: this.env._t("Price: High to Low") }, { id: 'name asc', title: this.env._t("Name: A to Z") }, { id: 'name desc', title: this.env._t("Name: Z to A") }, { id: 'create_date desc', title: this.env._t("Newly Arrived") }, { id: 'bestseller', title: this.env._t("Bestseller") }, { id: 'last_viewed', title: this.env._t("Recently Viewed") }]}};
    }
    get componentDefaultVal() {
        return this.props;
    }
}
TpDomainComponent.template = 'theme_prime.TpDomainComponent';
TpDomainComponent.components = { TpDropDown };

// we will add support for ControlPanel :)
registry.category('theme_components').add("TpRangeInput", TpRangeInput).add("TpBoolean", TpBoolean).add("TpCardGrid", TpCardGrid).add("TpDropDown", TpDropDown).add("TpActions", TpActions).add('TpImageUpload', TpImageUpload).add('TpComponentGroup', TpComponentGroup).add('TpDomainComponent', TpDomainComponent).add('TpSearchInput', TpSearchInput);