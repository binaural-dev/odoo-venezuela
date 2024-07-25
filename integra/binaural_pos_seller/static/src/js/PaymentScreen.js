odoo.define("binaural_pos_seller.PaymentScreen", function (require) {
  const PaymentScreen = require("point_of_sale.PaymentScreen");
  const Registries = require("point_of_sale.Registries");
  const NumberBuffer = require("point_of_sale.NumberBuffer");

  const BinauralPosSellerPaymentScreen = (PaymentScreen) =>
    class BinauralPosSellerPaymentScreen extends PaymentScreen {
      async selectSeller() {
        const employeesList = this.env.pos.sellers.filter((employee) => employee.is_seller !== false)
            .map((employee) => {
                return {
                    id: employee.id,
                    item: employee,
                    label: employee.name,
                    isSelected: false,
                };
            });
        const { confirmed, payload: newSeller } = await this.showPopup(
            'SelectionPopup',
            { title: this.env._t("Sellers"),
              list : employeesList,
            }
        );
        if (confirmed) {
            this.currentOrder.set_seller(newSeller);
        }
      }
      async _isOrderValid(isForceValidate){
        let Valid = super._isOrderValid(isForceValidate)
        if(!this.currentOrder.get_seller()){
          this.showPopup('ErrorPopup', {
            title: this.env._t('Seller Required'),
            body: this.env._t(
                'You must select a seller to complete the order.'
            ),
          })
          return false;
        }
        return Valid
      }
    };

  Registries.Component.extend(PaymentScreen, BinauralPosSellerPaymentScreen);
  return PaymentScreen;
});
