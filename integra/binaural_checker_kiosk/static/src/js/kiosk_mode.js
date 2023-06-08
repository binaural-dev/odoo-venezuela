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
								console.log($("#sh_product_image"))
								$('#sh_product_image').append(
									'<img class="img img-responsive" width="auto !important;" style="max-height:100%;max-width:100%;" src="data:image/jpeg;base64,' + result.sh_product_image + '" alt="Product Image" />'
								);
								$("#sh_product_barcode").html(result.sh_product_barcode);
								$("#sh_product_weight").html(result.sh_product_weight);
								$("#sh_product_pricelist").html(result.sh_product_pricelist);
								$("#sh_product_sale_price").html(result.sh_product_sale_price);
								$("#iva").html(result.sh_product_sale_price);
								$("#tax_base").html(result.iva);
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

								if (!result.price_with_iva) {
									$("#price_with_iva").parent().addClass("o_hidden");
								} else {
									$("#price_with_iva").parent().removeClass("o_hidden");
								}

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
								$("#fail").html(result.msg);
								$("#code").val("").replace('.', ',')
								$("#price_with_iva").val("");
								$("#sh_product_sale_price").val("");
								$("#iva").val("");
								$("#tax_base").val("");
								$("#foreign_sale_price_with_iva").val("");


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

        _onBarcodeScanned() {
            this._super.apply(this, arguments);
            
            const delay = $('#screen_delay').val() * 1000
            const searchButton = $(".o_mrp_kiosk_button_done")
            const screenDiv = $('#screen_div')
            const code = $("#code")
            
            setTimeout(function() {
                const lansdcapeValue = $('#display_landscape').val()
                const isLeft = lansdcapeValue == 'left'
                const isRight = lansdcapeValue == 'right'

                const isLeftOrRight = isLeft || isRight

                if (isLeftOrRight) {
				    screenDiv.addClass("col-12");
                    screenDiv.removeClass("col-7");
				}

                $("#main_div").addClass("o_hidden");
				$("#success").css("display", "none");

                //redisplay the reader input and message
                code.removeClass("d-none");
                searchButton.removeClass("d-none");
                screenDiv.removeClass("col-7");
				
            },delay)

            // hide the input and message from the reader
            searchButton.addClass("d-none");
            code.addClass("d-none");
            
        },
    })

    return CheckerKiosk;
})

