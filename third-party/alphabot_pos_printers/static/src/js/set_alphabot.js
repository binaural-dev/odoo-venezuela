odoo.define('alphabot.PosRestaurantOrder', function(require) {
    "use strict";

    const { Order } = require('point_of_sale.models');
    const Registries = require('point_of_sale.Registries');
    const Printer = require('point_of_sale.Printer').Printer;
    const core = require('web.core');
    const QWeb = core.qweb;
    var rpc = require('web.rpc');

    const alphaPosRestaurantOrder = (Order) => class PosRestaurantOrder extends Order {
        async printChanges(){
            let isPrintSuccessful = true;
			let image;
//			console.log("printChanges --------------------------------------------------------------");
            // se prepran las variables
            const d = new Date();
            let hours = '' + d.getHours();
            hours = hours.length < 2 ? ('0' + hours) : hours;
            let minutes = '' + d.getMinutes();
            minutes = minutes.length < 2 ? ('0' + minutes) : minutes;
            var fecha   = '' + d.toLocaleDateString() + ' ';
            let cashier =  this.pos.get_cashier();
            let cashier_name = cashier ? cashier.name : null;
            let table_name = this.pos.config.iface_floorplan ? this.getTable().name : false;
            let floor_name = this.pos.config.iface_floorplan ? this.getTable().floor.name : false;
            let cliente = this.get_partner();
            let cliente_name = cliente ? cliente.name : null;
            for (const printer of this.pos.unwatched.printers) {
                const changes = this._getPrintingCategoriesChanges(printer.config.product_categories_ids);
                if (changes['new'].length > 0 || changes['cancelled'].length > 0) {
                    const printingChanges = {
                        new: changes['new'],
                        cancelled: changes['cancelled'],
                        name: this.name || 'Orden',
                        table: table_name,
                        floor: floor_name,
                        fecha: fecha,
                        cashier: cashier_name || "",
                        guest_name: cliente_name,
                        time: {
                            hours,
                            minutes,
                        },
                    };
     			    const receipt = QWeb.render('KitchenReceipt', { changes: printingChanges });
     			    image = await printer.htmlToImg(receipt);
					var pos_name = this.pos.config.name;
					var user_name = this.pos.user.name;
					const printer_id = printer.config.id;
					const printer_name = printer.config.name;
					var cancelled = false;
					if (changes['cancelled'].length > 0 ) cancelled = true;
					if(!rpc.query({
						model: 'alphabot.printer.orders',
						method: 'action_set_image_to_print',
						args: [[printer_id], this.name, printer_id, image, cancelled, pos_name, user_name],
					})){
						isPrintSuccessful = false;
						}
                }
            }

//			if(isPrintSuccessful) console.log("printChanges OK");
//			else console.log("printChanges Error");

//            if(isPrintSuccessful)  this.env.pos.push_orders();

			return isPrintSuccessful;
        }

//		computeChanges: function(categories){
//		    var resp = _super_order.computeChanges.apply(this, arguments);
//
//		    console.log("computeChanges --------------------------------------------------------------");
//
//            var d = new Date();
//            var fecha   = '' + d.toLocaleDateString() + ' ';
//  		    console.log(fecha);
//            resp['fecha'] = fecha;
//
//            const cashier = this.pos.get_cashier();
//            var cashier_name = '';
//            if (cashier) { cashier_name = cashier.name;} ;
//            console.log(cashier);
//
//            resp['cashier'] = cashier_name;
//
//		    return resp;
//		}

    }

    Registries.Model.extend(Order, alphaPosRestaurantOrder);

});