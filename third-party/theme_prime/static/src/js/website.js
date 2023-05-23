/** @odoo-module **/

import "website.content.menu";
import { WebsiteRoot } from "website.root";
import publicWidget from "web.public.widget";
import config from "web.config";

const isMobileEnv = config.device.size_class <= config.device.SIZES.LG && config.device.touch;

// Enable bootstrap tooltip
$(document.body).tooltip({ selector: "[data-bs-toggle='tooltip']" });

// Back to top button
const backToTopButtonEl = document.querySelector(".tp-back-to-top");
if (backToTopButtonEl) {
    backToTopButtonEl.classList.add("d-none");
    if (!isMobileEnv) {
        const wrapwrapEl = document.getElementById("wrapwrap");
        wrapwrapEl.addEventListener("scroll", ev => {
            if (wrapwrapEl.scrollTop > 800) {
                backToTopButtonEl.classList.remove("d-none");
            } else {
                backToTopButtonEl.classList.add("d-none");
            }
        });
        backToTopButtonEl.addEventListener("click", ev => {
            ev.preventDefault();
            wrapwrapEl.scrollTo({ top: 0, behavior: "smooth" });
        });
    }
}

// Pricelist make selectable
WebsiteRoot.include({
    events: Object.assign({}, WebsiteRoot.prototype.events, {
        "click .dropdown-menu .tp-select-pricelist": "_onClickTpPricelist",
        "change .dropdown-menu .tp-select-pricelist": "_onChangeTpPricelist",
    }),
    _onClickTpPricelist: function (ev) {
        ev.preventDefault();
        ev.stopPropagation();
    },
    _onChangeTpPricelist: function (ev) {
        window.location = ev.currentTarget.value;
    },
});

// FIX: Affix header glitch on some devices having no footer pages(like checkout page).
publicWidget.registry.StandardAffixedHeader.include({
    _updateHeaderOnScroll: function (scroll) {
        if (!$("#wrapwrap footer").length) {
            this.destroy();
            return;
        }
        this._super(...arguments);
    }
});

publicWidget.registry.FixedHeader.include({
    _updateHeaderOnScroll: function (scroll) {
        if (!$("#wrapwrap footer").length) {
            this.destroy();
            return;
        }
        this._super(...arguments);
    }
});
