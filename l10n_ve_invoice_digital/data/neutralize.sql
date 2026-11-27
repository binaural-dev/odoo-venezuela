-- disable_l10n_ve_invoice_digital_integration
-- Clear the TFHKA credentials of every company when the database is neutralized (a copy restored
-- to staging or to a test environment), so the copy cannot reach the provider with the account of
-- production. This is what keeps the copy off TFHKA: tfhka.api.client needs the URL before any
-- request (_base_url raises without it) and the token (_token), and the neutralize.sql of the core
-- deactivates every cron, the digitalization queue included. The client does not check
-- database.is_neutralized.
UPDATE res_company
   SET username_tfhka = NULL,
       password_tfhka = NULL,
       url_tfhka = NULL,
       token_auth_tfhka = NULL;
