from odoo import api, fields, models, _
from ...tools import binaural_bcv_query

class ResCompany(models.Model):
    _inherit = "res.company"

    currency_provider = fields.Selection(
        selection_add=[("bcv", "Venezuelan Central Bank")]
    )

    can_update_habil_days = fields.Boolean(default=True)

    @api.model
    def _parse_bcv_data(self, available_currencies):
        """
        Parses currency rates from the BCV (Central Bank of Venezuela) website.
        This method is called by Odoo's multi-company currency update engine.
        
        :param available_currencies: List of currencies currently active in the system.
        :return: A dictionary mapping currency codes to their exchange rates and dates,
                 or an empty dict if the update is not applicable or fails.
        """
        # Always return a dictionary to prevent the calling method from crashing
        result = {}
        try:
            # We use the current company in the context
            current_date = fields.Date.context_today(self)
            
            # Check if today is a business day (Monday=1, Sunday=7)
            day = current_date.isoweekday()
            is_habil_day = day <= 5
            
            # Condition to skip update if it's a weekend and the company restricts it
            if not is_habil_day and self.can_update_habil_days:
                _logger.info("BCV Update: Skipping update because it is not a business day.")
                return result

            usd_rate_data = self.get_usd_rate_of_the_day_bcv()
            rate_value = usd_rate_data[0]
            rate_date = usd_rate_data[1]

            # Validate that we actually got a date and it matches today (or the expected date)
            if not rate_date or str(rate_date) != str(current_date):
                _logger.warning("BCV Update: The rate date found (%s) does not match today (%s).", rate_date, current_date)
                return result

            # result dictionary structure: { 'CURRENCY_CODE': (factor, date), ... }
            # Note: Odoo expects (1.0, date) for the base currency of the provider.
            result = {
                "USD": (1.0, rate_date),
                "VEF": (rate_value, rate_date) 
            }
        except Exception as e:
            _logger.error("BCV Update: Critical error parsing data: %s", e)
            
        return result
    
    @api.model
    def get_usd_rate_of_the_day_bcv(self):
        """
        Performs web scraping on the BCV website to retrieve the official USD exchange rate.
        
        :return: A tuple containing (float: rate value, date: date of the rate).
                 Returns (1.0, False) in case of connection or parsing errors.
        """
        disable_warnings(InsecureRequestWarning)
        URL = "https://www.bcv.org.ve/"
        current_date = fields.Date.context_today(self)

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

        try:
            # Using a 30-second timeout to prevent the process from hanging indefinitely
            response = requests.get(URL, verify=False, timeout=30, headers=headers)
            response.raise_for_status() # Ensure we got a 200 OK status
            
            soup = BeautifulSoup(response.text, "html.parser")

            # Extracting the USD value from the specific HTML ID used by BCV
            usd_container = soup.find(id="dolar")
            if not usd_container:
                _logger.error("BCV Update: No se encontró el contenedor 'dolar' en la web del BCV.")
                return (1.0, False)

            usd_value = (
                usd_container.text.replace("\n", "")
                .replace("USD", "")
                .replace(",", ".")
                .strip()
            )
            return (float(usd_value), current_date)
        except requests.exceptions.RequestException as e:
            _logger.error("BCV Update: Connection error to BCV website: %s", e)
            return (1.0, False)
        except Exception as e:
            _logger.error("BCV Update: Unexpected error during scraping: %s", e)
            return (1.0, False)

    @api.depends('country_id')
    def _compute_currency_provider(self):
        super(ResCompany, self)._compute_currency_provider()
        
        for record in self:
            if record.country_id and record.country_id.code == 'VE':
                record.currency_provider = 'bcv'
