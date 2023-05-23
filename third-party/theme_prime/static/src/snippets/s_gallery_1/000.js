/** @odoo-module **/

import publicWidget from "web.public.widget";
import { qweb } from "web.core";

publicWidget.registry.TpImageGallery = publicWidget.Widget.extend({
    selector: ".tp-image-gallery",
    events: {
        "click img": "_onClickImg",
    },
    _onClickImg: function (ev) {
        var self = this;
        var $cur = $(ev.currentTarget);

        var $images = $cur.closest(".tp-image-gallery").find("img");
        var size = 0.8;
        var dimensions = {
            min_width: Math.round(window.innerWidth * size * 0.9),
            min_height: Math.round(window.innerHeight * size),
            max_width: Math.round(window.innerWidth * size * 0.9),
            max_height: Math.round(window.innerHeight * size),
            width: Math.round(window.innerWidth * size * 0.9),
            height: Math.round(window.innerHeight * size)
        };

        var $img = ($cur.is("img") === true) ? $cur : $cur.closest("img");

        const milliseconds = $cur.closest(".tp-image-gallery").data("interval") || false;
        var $modal = $(qweb.render("website.gallery.slideshow.lightbox", {
            images: $images.get(),
            index: $images.index($img),
            dim: dimensions,
            interval: milliseconds || 0,
            id: _.uniqueId("tp_slideshow_"),
        }));
        $modal.on("hidden.bs.modal", function () {
            $(this).hide();
            $(this).siblings().filter(".modal-backdrop").remove(); // bootstrap leaves a modal-backdrop
            $(this).remove();
        });
        $modal.one("shown.bs.modal", function () {
            self.trigger_up("widgets_start_request", {
                editableMode: false,
                $target: $modal.find(".modal-body.o_slideshow"),
            });
        });
        $modal.appendTo(document.body);
        const modalBS = new Modal($modal[0], {keyboard: true, backdrop: true});
        modalBS.show();
    },
});
