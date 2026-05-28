import {registry} from '@web/core/registry'


export const convertAmountService = {
    dependencies: ["orm"],


    start(env, services) {
        const { orm } = services;
        
        return {
            async _syncForeignAmountDisplay(amount) {
                try {
                    const converted = await orm.call(
                        "pos.order",
                        "convert_amount",
                        [amount],
                        { context: { amount } }
                    );
                    return converted
                    
                    } catch (err) {
                        alert("Error converting total amount:", err);
                        return 0;
                }
            },
        }
        
    },
}

registry.category("services").add("convertForeignAmountService", convertAmountService);