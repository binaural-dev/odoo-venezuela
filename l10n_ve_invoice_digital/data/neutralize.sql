-- disable_l10n_ve_invoice_digital_integration
-- base/data/neutralize.sql already deactivates every cron (including the
-- digitalization queue) on a neutralized database; this clears the
-- credentials themselves so a stale token can't be reused if a cron is
-- ever reactivated by hand.
UPDATE res_company
   SET password_tfhka = NULL,
       token_auth_tfhka = NULL;
