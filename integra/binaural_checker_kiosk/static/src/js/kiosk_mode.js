odoo.define("sh_price_checker_kiosk.checker_action_kiosk_mode", function(require){
    "use strict";

    const KioskMode = require('sh_price_checker_kiosk.kiosk_mode');
    
    const CheckerKiosk = KioskMode.include({
        events: {
            'click .o_mrp_kiosk_button_done': function() {

				const mo_no = $("#code").val();
				if (mo_no) {
					/* Actions */
					this._rpc({
						model: 'product.product',
						method: 'all_scan_search',
						args: [mo_no],
					})
						.then(function (result) {
							if (result.issuccess == 1) {
								/* success msg */
								if ($('#display_landscape').val() == 'left' || $('#display_landscape').val() == 'right') {
									$('#screen_div').removeClass("col-12");
									$('#screen_div').addClass("col-7");
									$('#specification_div').removeClass("o_hidden");
								}

								$("#price_with_iva").html(result.price_with_iva)
								$("#main_div").removeClass("o_hidden");
								$("#sh_product_name").html(result.sh_product_name);
								$("#sh_product_code").html(result.sh_product_code);
								$("#sh_product_weight").html(result.sh_product_weight);
								$('#sh_product_image').html('');
	
								if(result.sh_product_image){
									$('#sh_product_image').append(
								 		'<img class="img img-responsive" width="auto !important;" style="max-height:60%;max-width:60%;" src="data:image/jpeg;base64,' + result.sh_product_image + '" alt="Product Image" />'
									);
								 }else {
									$("#sh_product_image").append(
										'<img class="img img-responsive" width="auto !important;" style="max-height:60%;max-width:60%;" src="/binaural_checker_kiosk/static/src/img/default.png" alt="Product Image" />'
									)
								}
							
								$("#sh_product_barcode").html(result.sh_product_barcode);
								$("#sh_product_weight").html(result.sh_product_weight);
								$("#sh_product_pricelist").html(result.sh_product_pricelist);
								$("#sh_product_sale_price").html(result.sh_product_sale_price);
								$("#iva").html(result.sh_product_sale_price);
								$("#tax_base").html(result.iva);
									$("#sh_company_logo_img").html("")
								$("#sh_company_logo_img").append(
									'<img class="img img-responsive img-fluid" style="width: 500px; heigth: 500px" t-attf-src="data:image/jpeg;base64,' + result.company_logo + '" alt="Company Logo" />'
								)
								$("#foreign_sale_price_with_iva").html(result.foreign_sale_price_with_iva);
								$("#quantity_available").html(result.product_qty);

								let count = 1
								result.sh_product_stock.forEach(object => {
									for (let key in object) {
										const obj = object[key];
										const warehouse_id = `#sh_product_warehouse_name_${count}`
										const stock_id = `#sh_product_stock_${count}`
										$(warehouse_id).html(key);
										$(stock_id).html(obj);
										count++;
									}
								})

								$("#logo_col-2").removeClass("o_hidden");

								$("#sh_product_category").html(result.sh_product_category);
								if (result.sh_product_attribute == '') {
									$('#attribute_tr').addClass('o_hidden');
								} else if (result.sh_product_attribute != '') {
									$('#attribute_tr').removeClass('o_hidden');
									$("#sh_product_attribute").html(result.sh_product_attribute);
								}

								if (result.sh_product_sale_description == '') {
									$('#sale_description_tr').addClass('o_hidden');
								} else if (result.sh_product_sale_description != '') {
									$('#sale_description_tr').removeClass('o_hidden');
									$("#sh_product_sale_description").html(result.sh_product_sale_description);
								}

								$("#success").css("display", "block");
								$("#success").html(result.msg);
								$("#fail").css("display", "none");
								$("#code").val("");
								$("#price_with_iva").val("");
								if (self.myvar) {
									clearTimeout(self.myvar);
								}
								const delay = $('#screen_delay').val() * 1000;

								self.myvar = setTimeout(function () {
									if ($('#display_landscape').val() == 'left' || $('#display_landscape').val() == 'right') {
										$('#screen_div').addClass("col-12");
                                        //redisplay the reader input and message
                                        $(".o_mrp_kiosk_button_done").removeClass("d-none");
                                        $("#code").removeClass("d-none");

										$('#screen_div').removeClass("col-7");
									}
									$("#main_div").addClass("o_hidden");
									$("#success").css("display", "none");
									$("#logo_col-2").addClass("o_hidden");
								}, delay);
							} else {
								/* Fail msg */
								if ($('#display_landscape').val() == 'left' || $('#display_landscape').val() == 'right') {
									$('#screen_div').addClass("col-12");
									$('#screen_div').removeClass("col-7");
								}

								$("#main_div").addClass("o_hidden");
								$("#success").css("display", "none");
								$("#fail").css("display", "block");
								$("#fail").html("no existe ningun producto asociado a este codigo de barras");


								setTimeout(function () {
									if ($('#display_landscape').val() == 'left' || $('#display_landscape').val() == 'right') {
										$('#screen_div').addClass("col-12");
                                        //redisplay the reader input and message
                                        $(".o_mrp_kiosk_button_done").removeClass("d-none");
                                        $("#code").removeClass("d-none");

										$('#screen_div').removeClass("col-7");
									}
									$("#main_div").addClass("o_hidden");
									$("#success").css("display", "none");
									$("#fail").css("display", "none");
								}, 3000);
							}

							/* Clear Inputs after result */
							$("#mono").val("");

                            // hide the input and message from the reader
                            $(".o_mrp_kiosk_button_done").addClass("d-none");
                            $("#code").addClass("d-none");
						});
				} else {
					alert("Please Enter Any barcode number");
				}
            }
        },

        async _onBarcodeScanned(barcode) {

				if (barcode) {
					/* Actions */
					this._rpc({
						model: 'product.product',
						method: 'all_scan_search',
						args: [barcode],
					})
						.then(function (result) {
							if (result.issuccess == 1) {
								/* success msg */
								if ($('#display_landscape').val() == 'left' || $('#display_landscape').val() == 'right') {
									$('#screen_div').removeClass("col-12");
									$('#screen_div').addClass("col-7");
									$('#specification_div').removeClass("o_hidden");
								}

								$("#price_with_iva").html(result.price_with_iva)
								$("#main_div").removeClass("o_hidden");
								$("#sh_product_name").html(result.sh_product_name);
								$("#sh_product_code").html(result.sh_product_code);
								$("#sh_product_weight").html(result.sh_product_weight);
								$('#sh_product_image').html('');
	
								if(result.sh_product_image){
									$('#sh_product_image').append(
								 		'<img class="img img-responsive" width="auto !important;" style="max-height:60%;max-width:60%;" src="data:image/jpeg;base64,' + result.sh_product_image + '" alt="Product Image" />'
									);
								 }else {
									$("#sh_product_image").append(
										'<img class="img img-responsive" width="auto !important;" style="max-height:60%;max-width:60%;" src="/binaural_checker_kiosk/static/src/img/default.png" alt="Product Image" />'
									)
								}
							
								$("#sh_product_barcode").html(result.sh_product_barcode);
								$("#sh_product_weight").html(result.sh_product_weight);
								$("#sh_product_pricelist").html(result.sh_product_pricelist);
								$("#sh_product_sale_price").html(result.sh_product_sale_price);
								$("#iva").html(result.sh_product_sale_price);
								$("#tax_base").html(result.iva);
									$("#sh_company_logo_img").html("")
								$("#sh_company_logo_img").append(
									'<img class="img img-responsive img-fluid" style="width: 500px; heigth: 500px" t-attf-src="data:image/jpeg;base64,' + result.company_logo + '" alt="Company Logo" />'
								)
								$("#foreign_sale_price_with_iva").html(result.foreign_sale_price_with_iva);

								let count = 1
								result.sh_product_stock.forEach(object => {
									for (let key in object) {
										const obj = object[key];
										const warehouse_id = `#sh_product_warehouse_name_${count}`
										const stock_id = `#sh_product_stock_${count}`
										$(warehouse_id).html(key);
										$(stock_id).html(obj);
										count++;
									}
								})

								$("#logo_col-2").removeClass("o_hidden");

								$("#sh_product_category").html(result.sh_product_category);
								if (result.sh_product_attribute == '') {
									$('#attribute_tr').addClass('o_hidden');
								} else if (result.sh_product_attribute != '') {
									$('#attribute_tr').removeClass('o_hidden');
									$("#sh_product_attribute").html(result.sh_product_attribute);
								}

								if (result.sh_product_sale_description == '') {
									$('#sale_description_tr').addClass('o_hidden');
								} else if (result.sh_product_sale_description != '') {
									$('#sale_description_tr').removeClass('o_hidden');
									$("#sh_product_sale_description").html(result.sh_product_sale_description);
								}

								$("#success").css("display", "block");
								$("#success").html(result.msg);
								$("#fail").css("display", "none");
								$("#code").val("");
								$("#price_with_iva").val("");
								if (self.myvar) {
									clearTimeout(self.myvar);
								}
								const delay = $('#screen_delay').val() * 1000;

								self.myvar = setTimeout(function () {
									if ($('#display_landscape').val() == 'left' || $('#display_landscape').val() == 'right') {
										$('#screen_div').addClass("col-12");
                                        //redisplay the reader input and message
                                        $(".o_mrp_kiosk_button_done").removeClass("d-none");
                                        $("#code").removeClass("d-none");

										$('#screen_div').removeClass("col-7");
									}
									$("#main_div").addClass("o_hidden");
									$("#success").css("display", "none");
									$("#logo_col-2").addClass("o_hidden");
								}, delay);
							} else {
								/* Fail msg */
								if ($('#display_landscape').val() == 'left' || $('#display_landscape').val() == 'right') {
									$('#screen_div').addClass("col-12");
									$('#screen_div').removeClass("col-7");
								}

								$("#main_div").addClass("o_hidden");
								$("#success").css("display", "none");
								$("#fail").css("display", "block");
								$("#fail").html("no existe ningun producto asociado a este codigo de barras");


								setTimeout(function () {
									if ($('#display_landscape').val() == 'left' || $('#display_landscape').val() == 'right') {
										$('#screen_div').addClass("col-12");
                                        //redisplay the reader input and message
                                        $(".o_mrp_kiosk_button_done").removeClass("d-none");
                                        $("#code").removeClass("d-none");

										$('#screen_div').removeClass("col-7");
									}
									$("#main_div").addClass("o_hidden");
									$("#success").css("display", "none");
									$("#fail").css("display", "none");
								}, 3000);
							}

							/* Clear Inputs after result */
							$("#mono").val("");

                            // hide the input and message from the reader
                            $(".o_mrp_kiosk_button_done").addClass("d-none");
                            $("#code").addClass("d-none");
						});
				} else {
					alert("Please Enter Any barcode number");
				}            
        },
    })

    return CheckerKiosk;
})