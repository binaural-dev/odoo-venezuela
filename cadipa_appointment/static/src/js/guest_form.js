/** @odoo-module **/
import { _t } from '@web/core/l10n/translation';
import publicWidget from "@web/legacy/js/public/public_widget";

const OriginalGuestForm = publicWidget.registry.GuestForm;

if (OriginalGuestForm) {
    publicWidget.registry.GuestForm = OriginalGuestForm.extend({            
        _validateAgeInForm: function ($form) {
            const originalResult = this._super.apply(this, arguments);
            if (!originalResult) return false;

            const $birth = $form.find('input.birthdate-input');
            const $error = $form.find('.age-error');
            const $relationSelect = $form.find('.type_relation-select');
            
            const $selectedOption = $relationSelect.find('option:selected');
            const isChild = $selectedOption.data('is-child') === true || $selectedOption.data('is-child') === 'true';

            const val = $birth.val();
            const parsed = this._parseYMD(val);

            if (!parsed) return true;

            const age = this._calcAge(parsed);
            
            if (age < 0) {
                const msg = _t('La fecha de nacimiento no puede ser en el futuro');
                $error.text(msg).show();
                $birth[0]?.setCustomValidity(msg);
                return false;
            }

            if (isChild) {
                const maxAge = parseInt(document.querySelector('#binaural_max_child_age')?.value || 0);
                const minAge = parseInt(document.querySelector('#binaural_min_child_age')?.value || 0);

                if (age > maxAge) {
                    const msg = _t(`La edad máxima para un niño es de ${maxAge} años`);
                    $error.text(msg).show();
                    $birth[0]?.setCustomValidity(msg);
                    return false;
                }
                
                if (age < minAge) {
                    const msg = _t(`El niño debe tener al menos ${minAge} años`);
                    $error.text(msg).show();
                    $birth[0]?.setCustomValidity(msg);
                    return false;
                }
            }

            $error.hide();
            $birth[0]?.setCustomValidity('');
            return true;
        }
    });
}