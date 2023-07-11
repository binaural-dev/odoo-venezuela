/** @odoo-module **/
import StripeOptions from '@payment_stripe/js/stripe_options';

export class StripeBinauralOptions extends StripeOptions {
    /**
     * Prepare the options to init the Stripe JS Object.
     *
     * This method serves as a hook for modules that would fully implement Stripe Connect.
     *
     * @param {object} processingValues
     * @return {object}
     */
    _prepareStripeOptions(processingValues) {
        return {
            // stripeAccount: processingValues.stripeAccount,
            countryCode: 'US',
        };
    };
}