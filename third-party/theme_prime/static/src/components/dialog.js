/** @odoo-module */
const { Component, onRendered, xml, useEffect, useState, onWillStart, useRef, toRaw } = owl;
import { useWowlService } from '@web/legacy/utils';
import { Dialog } from '@web/core/dialog/dialog';
import { TpRecordSelector } from './record_selection';
import { TpUiComponent } from './ui_component';
import { useService } from '@web/core/utils/hooks';
import { useCore } from '@droggol_theme_common/js/hooks';

export const Components = {
    TpRecordSelector: {
        Component: TpRecordSelector,
    },
    TpUiComponent: {
        Component: TpUiComponent,
    },
};

export class TpConfigDialog extends Dialog {
    setup() {
        super.setup();
        useEffect(() => {
            this.modalRef.el.classList.add('tp-snippet-config-dialog');
            if (this.modalRef.el.querySelector('.modal-dialog').classList.contains('modal-xl')) {
                this.modalRef.el.querySelector('.modal-dialog').classList.remove('modal-xl');
                this.modalRef.el.querySelector('.modal-dialog').classList.add('modal-fullscreen', 'p-0');
            }
        }, () => []);
    }
}
TpConfigDialog.components = {...Dialog.components};
TpConfigDialog.props = {...Dialog.props};

// Fucking TO-DO's for myself.

// To understand Below sh*t please read below comment
// I myself developed something phenomenal single handedly :)
// I've spread some sh*t in Configurator for example heavy lib.
// I've seen several spike while rendering DOM. Few OWL components which needs to be fixed.
// But it is not much serious.I will do some REF in next phase.
// We have used useState several places which is not necessary it's needs to be handled carefully.
// PublicWidgets needs to be REF. it was really terrible.
// If you're working in Droggol and you don't know what to do with any of JS file
// Feel free to contact KIG-ODOO
// If you're not from Droggol and your boss is telling you to copy things from theme prime and you don't like it.
// Feel free to send your CV to : https://www.droggol.com/jobs or hr@droggol.com
export class TpSnippetConfigDialog extends Component {
    setup() {
        super.setup();
        this.size = this.templateID ? 'xl' : 'md';
        this.footer = this.templateID ? false : true;
        this.contentClass = 'tp_snippet_config_dialog';
        this.supportedComponents = [];
        this.previewContainer = useRef('tp-preview-container');
        this.hasUiComponent = 'TpUiComponent' in this.props.components;
        this.hasSelectionComponent = 'TpRecordSelector' in this.props.components;
        this.componentService = useService('shared_component_service');
        this.tpWebsite = useService('website');
        this.videoURL = this.props.videoURL || 'https://youtu.be/iXAEbhTxXM4';
        this.prepareComponents();

        const { metadata: { title } } = this.tpWebsite.currentWebsite;
        this.path = title;
        this._coreProps = {
            updateSelectionComponentValue: this.updateSelectionComponentValue.bind(this),
            updateUiComponentValue: this.updateUiComponentValue.bind(this),
        };
        onWillStart(async () => {
            if (this.templateID) {
                let {content, name} = await this.componentService._fetchRecords({ model: 'ir.ui.view', extras: { templateID: this.templateID } });
                this.body = content;
                this.snippetName = name;
            }
        });
        useCore({});
    }
    getRecordFromData(records, recordID) {
        return records.find((record) => record.id === recordID);
    }
    updateSelectionComponentValue(key, value, name) {
        if (key) {
            this.state.TpRecordSelector[key] = value;
        } else {
            Object.keys(value).forEach(comp => {
                this.state.TpRecordSelector[comp] = value[comp];
            })
        }
        if (this.hasUiComponent && this.props.components.TpUiComponent.lazy) {
            let records = [];
            let defaults = { style: "s_tp_hierarchical_category_style_1", productListing: "bestseller", child: 4, limit: 4, brand: false, label: false, count: false, background: false };
            let configData = toRaw(this.state.TpUiComponent.categoryTabsConfig.records);
            let activeRecordID = false;
            value.forEach(res_ID => {
                let data = this.getRecordFromData(configData, res_ID);
                if (data) {
                    records.push(data);
                } else {
                    records.push({ ...defaults, id: res_ID });
                }
                activeRecordID = value[0];
            });
            this.updateUiComponentValue('categoryTabsConfig', { activeRecordID: activeRecordID, records: records });
        }
        this._reloadPreview();
    }
    updateUiComponentValue(key, value) {
        this.state.TpUiComponent[key] = value;
        this._reloadPreview();
    }
    toggleViewPort(mode) {
        if (this.previewContainer.el) {
            this.previewContainer.el.src = this.previewContainer.el.src;
        }
        this.state.isMobile = mode === 'mobile' ? true : false;
    }
    save () {
        this.props.save(this.state);
        this.props.close();
    }
    _onDiscardChange() {
        this.props.onDiscard();
        this.props.close();
    }
    prepareComponents () {
        let state = {isMobile: false};
        Object.keys(this.props.components).forEach(comp => {
            let value =  this.props.components[comp];
            this.forceVisible = value.forceVisible ? value.forceVisible : false;
            state[comp] = value && value.componentData && Object.keys(value.componentData).length ? value.componentData : {...value.defaultVal};
        });
        this.state = useState(state);
        Object.keys(this.props.components).forEach(comp => {
            let value = this.state[comp];
            this.supportedComponents.push({ ...Components[comp], props: { extras: { ...this.props.components[comp] }, componentData: value, allData: this.state, HasRecords: this.HasRecords }, name: comp});
        });
    }
    _onPreviewLoaded() {
        this.previewContainer.el.contentWindow.addEventListener('TP_WRAPPER_READY', (event) => {
            this.previewContainer.el.classList.add('tp-preview-loaded');
            this._reloadPreview();
        });
    }
    _reloadPreview() {
        if (this.previewContainer.el && this.previewContainer.el.contentDocument && this.previewContainer.el.contentDocument.querySelector('#tp_wrap')) {
            let wrapper = this.previewContainer.el.contentDocument.querySelector('#tp_wrap');
            wrapper.innerHTML = this.body;
            this.target = wrapper.querySelector('.tp-droggol-dynamic-snippet');
            this._setStateToDOM();
            wrapper.dispatchEvent(new CustomEvent('tp-reload'))
        }
    }
    _setStateToDOM() {
        _.each(this.state, (value, component) => {
            switch (component) {
                case 'TpRecordSelector':
                    this.target.setAttribute('data-selection-info', JSON.stringify(value));
                    break;
                case 'TpUiComponent':
                    this.target.setAttribute('data-ui-config-info', JSON.stringify(value));
                    break;
            }
        });
    }
    get templateID() {
        let { snippetID } = this.props;
        if (!snippetID) {
            return false;
        }
        let prefix = snippetID.includes('mega_menu') ? 'droggol_theme_common.' : 'theme_prime.';
        return prefix + snippetID;
    }
    get HasRecords() {
        let { TpRecordSelector } = this.state;
        if (this.forceVisible) {
            return true;
        }
        if (!TpRecordSelector) {
            return true;
        }
        let hasRec = TpRecordSelector.selectionType === 'advance' ? true : false;
        if (TpRecordSelector && TpRecordSelector.selectionType === 'manual' && TpRecordSelector.recordsIDs.length) {
            hasRec = true;
        }
        return hasRec;
    }
}
TpSnippetConfigDialog.template = 'theme_prime.snippetConfigDialog';
TpSnippetConfigDialog.components = { TpConfigDialog, TpRecordSelector};

export class TpSnippetConfigDialogWrapper extends Component {
    setup() {
        this.dialogs = useWowlService('dialog');
        onRendered(() => {
            this.dialogs.add(TpSnippetConfigDialog, this.props);
        });
    }
}
TpSnippetConfigDialogWrapper.template = xml``;