odoo.define('margin_zmart.productos', function (require) {
    "use strict";

    var core = require('web.core');
    var Widget = require('web.Widget');

    var QWeb = core.qweb;
    var rpc = require('web.rpc');

    var ProductosWidget = Widget.extend({
        template: 'nombre_del_modulo.productos_widget',

        start: function () {
            this._super.apply(this, arguments);
            this.render();
        },

        render: function () {
            var self = this;
            // Obtener los productos y sus precios de cada lista de tarifa
            rpc.query({
                model: 'product.product',
                method: 'search_read',
                domain: [],
                fields: ['name', 'lst_price'],
            }).then(function (products) {
                // Mostrar los productos en una tabla en el widget
                var $table = $('<table>');
                var $thead = $('<thead>').appendTo($table);
                var $tbody = $('<tbody>').appendTo($table);

                // Encabezados de la tabla
                var $trHead = $('<tr>').appendTo($thead);
                $('<th>').text('Producto').appendTo($trHead);
                $('<th>').text('Precio').appendTo($trHead);

                // Filas de la tabla con los productos y sus precios
                products.forEach(function (product) {
                    var $trBody = $('<tr>').appendTo($tbody);
                    $('<td>').text(product.name).appendTo($trBody);
                    $('<td>').text(product.lst_price).appendTo($trBody);
                });

                self.$el.append($table);
            });
        },
    });

    core.action_registry.add('productos', ProductosWidget);

    return ProductosWidget;
});
