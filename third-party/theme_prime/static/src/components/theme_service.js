/** @odoo-module **/

import { registry } from '@web/core/registry';
const { markup } = owl;

export const componentService = {
    dependencies: ['rpc'],
    start(env, { rpc }) {
        return {
            async _fetchRecords(params, extras) {
                let { routePath, fieldsToMarkup } = extras || {};
                routePath = routePath || '/theme_prime/tp_search_read';
                let fetchedRecords = await rpc(routePath, params);
                if (fieldsToMarkup && fieldsToMarkup.length) {
                    fetchedRecords.forEach(record => {
                        for (const fieldName of fieldsToMarkup) {
                            if (record[fieldName]) {
                                record[fieldName] = markup(record[fieldName]);
                            }
                        }
                    });
                }
                return fetchedRecords;
            },
        }
    }
}

registry.category('services').add('shared_component_service', componentService);