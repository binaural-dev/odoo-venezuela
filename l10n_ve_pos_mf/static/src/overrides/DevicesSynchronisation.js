/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import DevicesSynchronisation from "@point_of_sale/app/utils/devices_synchronisation";
import { Domain } from "@web/core/domain";

/**
 * Patch defensivo para evitar el error "Cannot read properties of undefined (reading 'plus')"
 * cuando algún registro sincronizado no tiene write_date válido (luxon DateTime).
 * 
 * Este error puede ocurrir cuando:
 * - Se sincronizan registros entre dispositivos
 * - Algún registro tiene write_date corrupto o indefinido
 * - Se intenta hacer write_date.plus({seconds: 1})
 */
patch(DevicesSynchronisation.prototype, {
    constructOrdersDomain() {
        const dynamicModels = this.dynamicModels;
        const recordsToCheck = Array.from(dynamicModels).reduce((acc, model) => {
            acc[model] = this.models[model].filter(
                (r) => !this.pos.data.opts.databaseTable[model]?.condition(r)
            );
            return acc;
        }, {});

        const recordIdsByModel = {};
        const domainByModel = Object.entries(recordsToCheck).reduce((acc, [model, records]) => {
            const serverRecs = records.filter((r) => r.isSynced);
            const ids = serverRecs.map((r) => r.id);
            const config = this.pos.config;
            const domains = [];

            if (ids.length === 0 && model !== "pos.order") {
                return acc;
            }

            recordIdsByModel[model] = ids;
            for (const record of serverRecs) {
                // Validación defensiva: verificar que write_date existe y es válido
                if (!record.write_date || typeof record.write_date.plus !== 'function') {
                    console.warn(`MF:: Registro con write_date inválido omitido`, {
                        model,
                        id: record.id,
                        write_date: record.write_date,
                        record
                    });
                    continue;
                }

                try {
                    const recordDateTime = record.write_date.plus({ seconds: 1 }).toUTC();
                    const recordDateTimeString = recordDateTime.toFormat("yyyy-MM-dd HH:mm:ss", {
                        numberingSystem: "latn",
                    });

                    let domain = new Domain([
                        ["id", "=", record.id],
                        ["write_date", ">=", recordDateTimeString],
                    ]);

                    if (model === "pos.order") {
                        domain = Domain.or([
                            domain,
                            new Domain([
                                ["id", "=", record.id],
                                ["state", "!=", record.state],
                            ]),
                        ]);
                    }

                    domains.push(domain);
                } catch (error) {
                    console.error(`MF:: Error procesando registro en constructOrdersDomain`, {
                        model,
                        id: record.id,
                        error
                    });
                }
            }

            let domain = Domain.or(domains);
            if (model === "pos.order") {
                domain = Domain.or([
                    domain,
                    new Domain([
                        ["id", "not in", ids],
                        ["state", "=", "draft"],
                        ["config_id", "in", [config.id, ...config.raw.trusted_config_ids]],
                    ]),
                ]);

                acc[model] = domain.toList();
            }

            return acc;
        }, {});

        return { domain: domainByModel, recordIds: recordIdsByModel };
    }
});