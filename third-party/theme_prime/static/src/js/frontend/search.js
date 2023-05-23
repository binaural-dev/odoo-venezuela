/** @odoo-module alias=droggol.product_serarch **/

import searchExports from '@website/snippets/s_searchbar/000';
import { Markup } from 'web.utils';
import { B2bMixin } from 'theme_prime.mixins';
import config from 'web.config';

let {searchBar} = searchExports;


searchBar.include(_.extend({}, B2bMixin, {

    events: _.extend({}, searchBar.prototype.events, {
        'click a[data-type]': '_onClickSearchResult'
    }),

    init: function () {
        this._super.apply(this, arguments);
        this.advanceMode = odoo.dr_theme_config.json_product_search.advance_search;
        this.search_reports = odoo.dr_theme_config.json_product_search.search_report;
    },

    async _fetch() {
        this.isB2bActive = this._isB2bModeEnabled();
        if (this.advanceMode) {
            this.searchType = 'droggol';
            const res = await this._rpc({
                route: '/website/dr_search',
                params: {
                    'term': this.$input.val(),
                    'max_nb_chars': Math.round(Math.max(this.autocompleteMinWidth, parseInt(this.$el.width())) * 0.22),
                    'options': this.options,
                    'device_type': config.device.isMobile ? 'mobile': 'desktop',
                }
            });

            if (this.search_reports) {
                this.searchReportData = {
                    'search_term': this.$input.val(),
                    'category_count': res.categories.results.length,
                    'product_count': res.products.results.length,
                    'autocomplete_count': res.autocomplete.results_count,
                    'suggestion_count': res.suggestions.results_count,
                }
            }

            this._markupRecords(res.products.results);
            this._markupRecords(res.categories.results);
            this._markupRecords(res.suggestions.results);
            this._markupRecords(res.autocomplete.results);
            if (res.global_match) {
                res.global_match['name'] = Markup(res.global_match['name'])
            }
            this.results = res || {};
            return res
        } else {
            return this._super.apply(this, arguments);
        }
    },

    _markupRecords: function (results) {
        const fieldNames = ['name', 'description', 'extra_link', 'detail', 'detail_strike', 'detail_extra'];
        results.forEach(record => {
            for (const fieldName of fieldNames) {
                if (record[fieldName]) {
                    if (typeof record[fieldName] === "object") {
                        for (const fieldKey of Object.keys(record[fieldName])) {
                            record[fieldName][fieldKey] = Markup(record[fieldName][fieldKey]);
                        }
                    } else {
                        record[fieldName] = Markup(record[fieldName]);
                    }
                }
            }
        });
    },

    _onKeydown: function (ev) {
        if ([$.ui.keyCode.DOWN, $.ui.keyCode.UP].includes(ev.which) && this.$menu && this.advanceMode) {
            ev.preventDefault();
            const focusableEls = [this.$input[0], ...[...this.$menu[0].children].filter((item) => { return item.classList.contains('dropdown-item')})];
            const focusedEl = document.activeElement;
            const currentIndex = focusableEls.indexOf(focusedEl) || 0;
            const delta = ev.which === $.ui.keyCode.UP ? focusableEls.length - 1 : 1;
            const nextIndex = (currentIndex + delta) % focusableEls.length;
            const nextFocusedEl = focusableEls[nextIndex];
            nextFocusedEl.focus();
        } else { this._super.apply(this, arguments); }
    },

    _onClickSearchResult: function (ev) {
        if (this.search_reports) {
            var $searchResult = $(ev.currentTarget);
            var search_type = $searchResult.data('type');
            this.searchReportData['clicked_type'] = search_type;
            this.searchReportData['clicked_href'] = $searchResult.attr('href');
            if (search_type == 'product') {
                this.searchReportData['clicked_string'] = $searchResult.find('.h6').text().trim();
            } else {
                this.searchReportData['clicked_string'] = $searchResult.text().trim();
            }
            this.searchReportData['device_type'] = config.device.isMobile ? 'mobile': 'desktop';
            this._rpc({
                route: '/website/dr_search/add_report',
                params: this.searchReportData
            });

        }
    },
}));

export default {
    searchBar: searchBar,
};
