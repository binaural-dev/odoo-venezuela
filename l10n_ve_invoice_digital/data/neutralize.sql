-- disable_l10n_ve_invoice_digital_integration
-- The digitalization queue cron (ir_cron_tfhka_digitalization_queue) and the
-- in-code guard against database.is_neutralized (tfhka.api.client) already
-- stop outbound calls; this only clears the credentials so a stale token
-- can't be reused if the guard is ever bypassed by hand.
UPDATE res_company
   SET password_tfhka = NULL,
       token_auth_tfhka = NULL;
