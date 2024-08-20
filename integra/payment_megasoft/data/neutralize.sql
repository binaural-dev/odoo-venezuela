-- disable megasoft payment provider
UPDATE payment_provider
   SET megasoft_url = NULL,
       megasoft_user = NULL,
       megasoft_password = NULL,
       megasoft_cod_afiliation = NULL;
