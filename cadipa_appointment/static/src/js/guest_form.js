/** @odoo-module **/
import { _t } from '@web/core/l10n/translation';
import publicWidget from "@web/legacy/js/public/public_widget";

const OriginalGuestForm = publicWidget.registry.GuestForm;

if (OriginalGuestForm) {
    publicWidget.registry.GuestForm = OriginalGuestForm.extend({            
        /**
         * Extended function to add new age validations.
         */
        _validateAgeInForm: function ($form) {
            const originalResult = this._super.apply(this, arguments);

            if (!originalResult) {
                return false;
            }

            const $birth = $form.find('input.birthdate-input');
            const $error = $form.find('.age-error');
            const clasification = $form.find('.guest-type-select').val();
            const guest_type = $form.find('.type_relation-select').val();
            
            const val = $birth.val();
            
            const parsed = this._parseYMD(val);

            if (!parsed) {
                return true;
            }
            const minAge = parseInt(document.querySelector('#binaural_min_child_age')?.value || 0);
            const age = this._calcAge(parsed);

            if (age < 0) {
                $error.text(_t('La fecha de nacimiento no puede ser en el futuro')).show();
                $birth[0]?.setCustomValidity(_t('The birthdate cant be in the future'));
                return false;
            }

            if (age < minAge) {
                $error.text(_t('El niño debe tener al menos 9 años')).show();
                $birth[0]?.setCustomValidity(_t('The child must be at least 9 years old'));
                return false;
            }
            return true;
        }
    });
}