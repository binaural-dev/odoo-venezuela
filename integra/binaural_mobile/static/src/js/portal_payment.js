/** @odoo-module */

import publicWidget from "@web/legacy/js/public/public_widget";
import { _t } from "@web/core/l10n/translation";
import { Dialog } from "@web/core/dialog/dialog";
import { jsonrpc } from "@web/core/network/rpc_service";

publicWidget.registry.PaymentsPortalForm = publicWidget.Widget.extend({
  selector: ".payments_portal_form",
  events: {
    "change #clients": "_onChangeClients",
    "change #diary": "_onChangeFiscal",
    "change #diary_pay": "_onChangeDairy_payment",
    "click #exit_payment": "_onClickExit_payment",
    "click #save_payment": "_onClickSave_payment",
    "change .select_invoice": "_onChangeSelectInvoice",
    "click .delete_payment": "_onClickDelete_payment",
    "click .edit_payment": "_onClickEdit_payment",
    "click #process_payment": "_onClickProcess_payment",
    "change #use_credit": "onClickUse_credit",
    "change #attach_input": "onChangeAttachment",
    "click #remove_attach": "onClickRemoveAttach",
    "change #payday": "_onChangeDateCurrency",
    "change #amount_to_payment": "_onChangeAmountPayment",
  },
  init: function (parent, options) {
    this._super.apply(this, arguments);
    this.partners = [];
  },
  start: function () {
    const self = this;

    this.fields_clear();
    this.ClearTotalRetentions();
    this.Empty_inputs();
    $("#diary").val("");

    $("#clients").select2({
      maximumInputLength: 35,
      minimumInputLength: 0,
      maximumSelectionSize: 1,
      ajax: {
        url: "/payments/client",
        dataType: "json",
        data: (term) => ({ query: term }),
        results: (data) => {
          const { status, data: dt } = data;
          const is400e = status === 404;
          if (is400e) return;
          const ret = [];
          dt.forEach(client => { 

            const { id: clientId } = client;
            const isExistclient = ret.find(
              (client) => client.id === clientId
            );

            if (isExistclient) return;

            ret.push({
              id: client.id,
              text: client.display_name,
              isNew: false,
            });
            self.partners.push(client);
          });
          return { results: ret };
        },
      },
    });

    ["#payday"].forEach(function (id) {
      const today = new Date().toISOString().slice(0, 10);
      $(id).val(today);
      $(id).attr("max", today);
      $(id).attr("min", "2000-01-01");
    });

    $("#reference_number").attr("maxlength", "20");

    ["#amount_to_payment"].forEach(function (id) {
      $(id).attr("maxlength", "10");
      $(id).keypress(function (e) {
        var currentValue = $(this).val();
        var regex = new RegExp("^[0-9]*([.][0-9]*)?$");
        var str = String.fromCharCode(!e.charCode ? e.which : e.charCode);
        if (regex.test(currentValue + str)) {
          if (str === "." && currentValue.indexOf(".") !== -1) {
            e.preventDefault();
            return false;
          }
          return true;
        }
        e.preventDefault();
        return false;
      });
    });
  },

  fields_clear: function () {
    $(".table-clear").empty();
    $(".label-clear").text("0.00");
    $(".value-clear").val(0);
    $("#use_credit").prop("checked", false);
    $("#remove_attach").attr("disabled", true);
    $(".hidden_pay").hide();
  },

  _onChangeClients: function (ev) {
    if ($("#clients").val() != "") {
      let decimal_number = +$("#decimal").val();
      let client = selectedPartner(this.partners, parseInt(ev.target.value));
      this.fields_clear();
      let { credit_partner } = client;
      if (credit_partner < 0) {
        const amountPartner = (credit_partner * -1).toFixed(decimal_number);
        $("#positive_balance_l").text(amountPartner);
        $("#positive_balance").val(amountPartner);
      }
      $("#diary").val("");
      $(".disabled-input").attr("disabled", false);
      this.CalculateRemainingAmount();
    }
  },

  ClearTotalRetentions: function () {
    $(".clear-total-retention").val(0);
    $(".clear-total-retention-l").text("0.00");
  },

  _onChangeFiscal: async function (ev) {
    if ($("#diary").val() != "") {
      const partner_id = $("#clients").val();
      const type_dairy = $("#diary").val();
      const invoices = await jsonrpc("/payments/account_move", {
        partner_id: partner_id,
        type_dairy: type_dairy,
      });
      this.ClearTotalRetentions();
      $("#requireReceipt").val("");
      const { data, status, taxpayer_type, msg } = invoices
      const is204 = status === 204;
      const is400 = status === 400;
      if(is400){
        Dialog.alert(this,msg, { title: 'Error' });
        return;
      }
      if (is204) {
        const tbody = $("#notes_invoices_results");
        tbody.empty();
        let msg_error = _t("No se han encontrado resultados.");
        tbody.append(`
                  <tr>
                      <td>
                          <div class="d-flex justify-content-center">
                              <div class="alert alert-danger col-sm-10" style="text-align:center; font-weight:bolder;" role="alert">
                                  ${msg_error}
                              </div>
                          </div>
                      </td>
                  </tr>
                  `);
        return;
      }

      const requireReceipt = data[0]["journal_id"][2];
      $("#requireReceipt").val(requireReceipt);
      this.CalculateRemainingAmount();
      this.build_table_invoices(data, taxpayer_type)
    }
  },

  build_table_invoices: function(invoices,taxpayer_type) {
    const tbody = $("#notes_invoices_results");
    tbody.empty();
    let decimal_number = +$("#decimal").val();
    const symbol = $("#symbol").val();
    let symbolAfter = "";
    let symbolBefore = "";

    if ($("#position").val() == "after") {
      symbolAfter = symbol;
    } else {
      symbolBefore = symbol;
    }

    const amountL = _t("Importe adeudado:");
    const taxableBaseL = _t("Base imponible: ");
    const amountDetailedL = _t("Monto retenido: ");
    const ivaDifL = _t("Diferencia de IVA:");
    const note = _t("Nota:");

    invoices.forEach((line) => {
      let {
        amount_total,
        amount_untaxed,
        amount_tax,
        id,
        name,
        journal_id,
        amount_residual,
      } = line;
      
      const lines_ordered_by_maturity_date = line.line_ids.sort(function (
        a,
        b
      ) {

        
        if (!(a.date_maturity && b.date_maturity)) return;

        const a_date = a.date_maturity.split("/");
        [a_date[0], a_date[1]] = [a_date[1], a_date[0]];

        const b_date = b.date_maturity.split("/");
        [b_date[0], b_date[1]] = [b_date[1], b_date[0]];

        return new Date(a_date) - new Date(b_date);
      });
      const first_expired_line = lines_ordered_by_maturity_date[0];
      const first_expired_line_amount_residual = first_expired_line["amount_residual"].toFixed(decimal_number);

      const date_maturity = first_expired_line["date_maturity"];
      const date_maturity_elem = date_maturity ? `(${date_maturity})` : '';

      amount_residual = amount_residual.toFixed(decimal_number);
      amount_total = amount_total.toFixed(decimal_number);
      let tr_open = ` 
                      <tr>
                      <td id="invoice">
                          <div class="d-flex justify-content-between">
                              <div>
                                  <input class="form-check-input mx-auto select_invoice" type="checkbox"/>
                                  <label class="form-label ">${name}</label>
                                  <input type="hidden" id="invoice_id" value="${id}">

                                  <br/>
                                  
                                  <label class="form-label">Importe adeudado (cuota): </label>
                                  <label class="form-text text-primary">${symbolBefore}</label>
                                  <label class="form-text text-primary">
                                    ${first_expired_line_amount_residual} 
                                  </label>
                                  <label class="form-text">${date_maturity_elem}</label>
                              </div>
                              <div>
                                  <label class="form-text ">Total: </label>
                                  <label class="form-text text-primary">${symbolBefore}</label>
                                  <label class="form-text text-primary">${amount_total}</label>
                                  <input id="amount_t" type="hidden" value="${amount_total}"/>
                                  <label class="form-text text-primary">${symbolAfter}</label>
                                  <br/>
                                  <label class="form-text ">${amountL}</label>
                                  <label class="form-text text-primary">${symbolBefore}</label>
                                  <label class="form-text text-primary">${amount_residual}</label>
                                  <input id="amount_r" type="hidden" value="${amount_residual}"/>
                                  <label class="form-text text-primary">${symbolAfter}</label>
                              </div>    
                          </div>
                          `;

      let tr_close = `</td></tr>`;

      $("#notes_invoices").text(_t("Notas:"));

      if (journal_id[2] && taxpayer_type != 'ordinary'){
        const {
          currency_foreign,
          is_foreign,
          foreign_total_billed,
          foreign_taxable_income,
        } = line;
        let retencion = parseFloat($("#withholding").val());
        let amount_detained = (amount_tax * retencion) / 100;
        amount_detained = amount_detained.toFixed(decimal_number);
        let dif_iva = amount_tax - amount_detained;
        dif_iva = dif_iva.toFixed(decimal_number);
        let amount_detained_vef,
          dif_iva_vef = null;
        let amount_detained_vef_line,
          dif_iva_vef_line,
          amount_tax_vef_line,
          amount_untaxed_vef_line = ``;

        if (!is_foreign) {
          let decimal_places = +$("#currency_foreign_id").val();
          let iva_vef = (
            foreign_total_billed - foreign_taxable_income
          ).toFixed(decimal_places);
          amount_detained_vef = ((iva_vef * retencion) / 100).toFixed(
            decimal_places
          );
          dif_iva_vef = (iva_vef - amount_detained_vef).toFixed(
            decimal_places
          );
          amount_untaxed_vef_line = `
                          <label class="form-text" style="opacity:0;">${taxableBaseL}</label>
                          <label class="form-text text-secondary">${foreign_taxable_income
                            .toFixed(decimal_places)
                            .replace(".", ",")}</label>
                          <label class="form-text text-secondary">${currency_foreign}</label>
                      `;
          amount_tax_vef_line = `
                          <label class="form-text text-secondary">${iva_vef.replace(
                            ".",
                            ","
                          )}</label>
                          <label class="form-text text-secondary">${currency_foreign}</label>
                      `;
          amount_detained_vef_line = `
                          <label class="form-text" style="opacity:0;">${amountDetailedL}</label>
                          <label class="form-text text-secondary">${amount_detained_vef.replace(
                            ".",
                            ","
                          )}</label>
                          <label class="form-text text-secondary">${currency_foreign}</label>
                          <input type="hidden" id="amount_retention_vef" value="${amount_detained_vef}"/>
                      `;
          dif_iva_vef_line = `
                          <label class="form-text text-secondary">${dif_iva_vef.replace(
                            ".",
                            ","
                          )}</label>
                          <label class="form-text text-secondary">${currency_foreign}</label>
                      `;
        }

        let tr_selected = `<div id="to_pay" style="display: none;">
                                      <hr width="100%" />
                                      <div class="d-flex justify-content-between">
                                          <div>
                                              <label class="form-text ">${taxableBaseL}</label>
                                              <label class="form-text text-primary">${symbolBefore}</label>
                                              <label class="form-text text-primary">${amount_untaxed}</label>
                                              <label class="form-text text-primary">${symbolAfter}</label>
                                              
                                          </div>
                                          <div>
                                              <label class="form-text ">IVA:</label>
                                              <label class="form-text text-primary">${symbolBefore}</label>
                                              <label class="form-text text-primary">${amount_tax}</label>
                                              <label class="form-text text-primary">${symbolAfter}</label>
                                              
                                          </div>
                                      </div>
                                      <div class="d-flex justify-content-between">
                                          <div>
                                              ${amount_untaxed_vef_line}
                                          </div>
                                          <div>
                                              ${amount_tax_vef_line}
                                          </div>
                                      </div>
                                      <div class="d-flex justify-content-between">
                                          <div>
                                              <label class="form-text ">${amountDetailedL}</label>
                                              <label class="form-text text-primary">${symbolBefore}</label>
                                              <label class="form-text text-primary" id="amount_retention">${amount_detained}</label>
                                              <label class="form-text text-primary">${symbolAfter}</label>
                                          </div>
                                          <div>
                                              <label class="form-text ">${ivaDifL}</label>
                                              <label class="form-text text-primary">${symbolBefore}</label>
                                              <label class="form-text text-primary">${dif_iva}</label>
                                              <label class="form-text text-primary">${symbolAfter}</label>
                                          </div>
                                      </div>
                                      <div class="d-flex justify-content-between">
                                          <div>
                                              ${amount_detained_vef_line}
                                          </div>
                                          <div>
                                              ${dif_iva_vef_line}
                                          </div>
                                      </div>
                                      <hr width="100%" />
                                      <div class="d-flex justify-content-center">
                                          <div class="col-sm-4">
                                              <label class="form-text">${note}</label>
                                              <input type="text" class="form-control" id="note_payment"/>
                                          </div>
                                      </div>
                                  </div>`;
        tr_open += tr_selected;
        $("#notes_invoices").text(_t("Facturas:"));
      }
      else (journal_id[2] && taxpayer_type == 'ordinary');{
        const { currency_foreign, is_foreign, foreign_total_billed, foreign_taxable_income } = line
        let retencion = parseFloat($("#withholding").val())
        let amount_detained = amount_tax * retencion / 100
        amount_detained = amount_detained.toFixed(decimal_number)
        let dif_iva =  amount_tax - amount_detained
        dif_iva = dif_iva.toFixed(decimal_number)
        amount_tax = amount_tax.toFixed(decimal_number)
        amount_untaxed = amount_untaxed.toFixed(decimal_number)
        let amount_detained_vef, dif_iva_vef = null
        let amount_detained_vef_line, dif_iva_vef_line, amount_tax_vef_line,amount_untaxed_vef_line = ``

        if(!is_foreign){
            let decimal_places = +$("#currency_foreign_id").val()
            let iva_vef = (foreign_total_billed - foreign_taxable_income).toFixed(decimal_places)
            amount_detained_vef = (iva_vef * retencion / 100).toFixed(decimal_places)
            dif_iva_vef = (iva_vef - amount_detained_vef).toFixed(decimal_places)
            amount_untaxed_vef_line = `
                <label class="form-text" style="opacity:0;">${taxableBaseL}</label>
                <label class="form-text text-secondary">${foreign_taxable_income.toFixed(decimal_places).replace('.', ',')}</label>
                <label class="form-text text-secondary">${currency_foreign}</label>
            `
            amount_tax_vef_line = `
                <label class="form-text text-secondary">${iva_vef.replace('.', ',')}</label>
                <label class="form-text text-secondary">${currency_foreign}</label>
            `
            amount_detained_vef_line = `
                <label class="form-text" style="opacity:0;">${amountDetailedL}</label>
                
                <label class="form-text text-secondary">${amount_detained_vef.replace('.', ',')}</label>
                <label class="form-text text-secondary">${currency_foreign}</label>
                <input type="hidden" id="amount_retention_vef" value="0"/>
            `
            dif_iva_vef_line = `
                <label class="form-text text-secondary">${dif_iva_vef.replace('.', ',')}</label>
                <label class="form-text text-secondary">${currency_foreign}</label>
            `
        }
        if(journal_id[2]){
        let tr_selected = `<div id="to_pay" style="display: none;">
                            <hr width="100%" />
                            <div class="d-flex justify-content-between">
                                <div>
                                    <label class="form-text ">${taxableBaseL}</label>
                                    <label class="form-text text-primary">${symbolBefore}</label>
                                    <label class="form-text text-primary">${amount_untaxed}</label>
                                    <label class="form-text text-primary">${symbolAfter}</label>
                                    
                                </div>
                                <div>
                                    <label class="form-text ">IVA:</label>
                                    <label class="form-text text-primary">${symbolBefore}</label>
                                    <label class="form-text text-primary">${amount_tax}</label>
                                    <label class="form-text text-primary">${symbolAfter}</label>
                                    
                                </div>
                            </div>
                            <div class="d-flex justify-content-between">
                                <div>
                                    ${amount_untaxed_vef_line}
                                </div>
                                <div>
                                    ${amount_tax_vef_line}
                                </div>
                            </div>
                            <div class="d-flex justify-content-between">
                                <div>
                                    <label class="form-text text-primary" id="amount_retention"></label>
                                    <label class="form-text text-primary">${symbolAfter}</label>
                                </div>
                                
                            </div>
                            <div class="d-flex justify-content-between">
                                <div style="display: none;">
                                    ${amount_detained_vef_line}
                                </div>
                                <div>
                                    
                                </div>
                            </div>
                            <hr width="100%" />
                            <div class="d-flex justify-content-center">
                                <div class="col-sm-4">
                                    <label class="form-text">${note}</label>
                                    <input type="text" class="form-control" id="note_payment"/>
                                </div>
                            </div>
                        </div>`
        tr_open += tr_selected
      }
        else
        {
          let tr_selected = ``
          tr_open += tr_selected
        }
        $("#notes_invoices").text(_t("Facturas:"))
    }

      let tr_add = tr_open + tr_close;
      tbody.append(tr_add);
    });
  },

  _onChangeDairy_payment: function (ev) {
    this.SetSymbolCurrencyInput();
  },

  SetSymbolCurrencyInput: async function () {
    const dairy = $("#diary_pay").val();
    if (dairy != "") {
      const dairySym = await jsonrpc(
        "/payments/get_symbol_currency",
        
        {
          dairy_id: dairy,
          exist_igtf: $("#igtf_pay").length,
        }
      );
      const { data, status, msg } = dairySym;
      const is404 = status === 404;
      if(is404){
        Dialog.alert(this,msg, { title: 'Error' });
        return;
      }

      $("#currency").val(data[0]);
      $("#symbol-dairy").text(data[1]);
      $("#position_symbol").val(data[2]);
      $("#required_igtf").val(data[3]);
      $(".disabled-pay").attr("disabled", false);
      if ($("#igtf_pay").length) {
        if (
          data[1] == "$" &&
          $("#requireReceipt").val() == "true" &&
          data[3]
        ) {
          $(".igtf_input").show();
          this.CalculateIGTF();
        } else {
          $(".igtf_input").hide();
          $("#igtf_pay").val("");
        }
      }
    } else {
      $(".disabled-pay").attr("disabled", true);
      this.Empty_inputs();
    }
    this.SetRateCurrency();
  },

  _onChangeAmountPayment: function (ev) {
    this.CalculateIGTF();
  },

  _onChangeDateCurrency: function (ev) {
    this.SetRateCurrency();
  },

  SetRateCurrency: async function () {
    const currencyDay = await jsonrpc(
      "/payments/get_currency_rate",
      
      {
        date_pay: $("#payday").val(),
        currency: $("#currency").val(),
      }
    );
    const { data, status } = currencyDay;
    const is400 = status === 400;
    if (is400) return;

    $("#rate-day").val(data[0] > data[1] ? data[0] : data[1]);
  },

  Empty_inputs: function () {
    [
      "#diary_pay",
      "#amount_to_payment",
      "#reference_number",
      "#pay_edit",
      "#currency",
      "#position_symbol",
      "#igtf_pay",
      "#required_igtf",
    ].forEach(function (id) {
      $(id).val("");
    });
    $("#symbol-dairy").text("-");
    $(".igtf_input").hide();
  },

  Set_day_today: function () {
    const today = new Date().toISOString().slice(0, 10);
    $("#payday").val(today);
  },

  _onClickExit_payment: function (ev) {
    this.Empty_inputs();
    this.Set_day_today();
    let inputsRequest = [
      "#diary_pay",
      "#amount_to_payment",
      "#reference_number",
    ];
    inputsRequest.forEach(function (id) {
      $(id).removeClass("is-invalid");
    });
    $(".disabled-pay").attr("disabled", true);
  },

  _onClickSave_payment: async function (ev) {
    let inputsRequest = ['#diary_pay', '#amount_to_payment', '#reference_number',]
    let emptyInput = ''
    inputsRequest.forEach(function (id) {
        if ($(id).val().trim() === '') {
            emptyInput = id;
            return false;
        }
        $(id).removeClass('is-invalid');
    });
    if (emptyInput) {
      $(emptyInput).addClass('is-invalid')
      return
    }
    const tbody = $("#pay_methods");
    let decimal_number = +$("#decimal").val();
    const text = $("#diary_pay").find(":selected").text();
    const text_val = $("#diary_pay").find(":selected").val();
    let payment = parseFloat(+$("#amount_to_payment").val()).toFixed(
      decimal_number
    );
    const reference = $("#reference_number").val();
    const date = $("#payday").val();
    const $symbol = $("#symbol");
    const currency = $("#currency").val();
    const positionSymbol = $("#position").val();
    const igtfAmount = +$("#igtf_pay").val();
    let igtf_include = ``;
    let convert = "";
    let convert_symbol = "";

    const symbolAfter = positionSymbol === "after" ? $symbol.val() : "";
    const symbolBefore = positionSymbol === "before" ? $symbol.val() : "";

    if ($("#currency_id").val() != currency) {
      const convertedCurrency = await jsonrpc(
        "/payments/convert_currency",
        {
          currency: currency,
          amount: payment,
        }
      );
      let { data, status } = convertedCurrency;
      const is400 = status === 400;
      if (is400) return;

      convert = parseFloat(+$("#amount_to_payment").val()).toFixed(
        +$("#currency_foreign_id").val()
      );

      payment = data.toFixed(decimal_number);

      const symbolConverted = $("#symbol-dairy").text();
      const positionConverted = $("#position_symbol").val();

      const symbolAfterConverted =
        positionConverted === "after" ? symbolConverted : "";
      const symbolBeforeConverted =
        positionConverted === "before" ? symbolConverted : "";

      convert_symbol = `${symbolBeforeConverted} ${convert} ${symbolAfterConverted}`;
    }

    const paySymbol = `${symbolBefore} ${payment} ${symbolAfter}`;

    if ($("#pay_edit").val() != "") {
      const trPosition = +$("#pay_edit").val();
      const $table = $("#pay_methods");
      const $cell = $table.find("tr").eq(trPosition);
      $cell.remove();
    }

    if (igtfAmount != "" && $("#requireReceipt").val() == "true") {
      igtf_include = `
                <br/>
                <label class="form-text" style="padding-left:87px;">IGTF Sugerido: $ ${igtfAmount.toFixed(
                  decimal_number
                )}</label>
                <input type="hidden" id="igtf_amount" value="${igtfAmount}"/>
                `;
    }
    tbody.append(`
            <tr>
                <td>
                    <div class="d-flex justify-content-between">
                        <div>
                            <button type="button" class="btn btn-outline-danger fa fa-times delete_payment"></button>
                            <button type="button" class="btn btn-outline-primary fa fa-pencil edit_payment"></button>
                            <input type="hidden" value="${text_val}" id="dairy_val"/>
                            <label class="form-label">${text}</label>
                            <input type="hidden" id="reference" value="${reference}"/>
                            <input type="hidden" id="date_to_pay" value="${date}"/>
                            ${igtf_include}
                        </div>
                        <div>
                            <input type="hidden" id="currency_" value="${currency}"/>
                            <label class="form-text text-primary" id="payment_l">${paySymbol}</label>
                            <input type="hidden" id="payment" value="${payment}"/><br/>
                            <label class="form-text text-secondary" id="payment_convert_l">${convert_symbol}</label>
                            <input type="hidden" id="payment_convert" value="${convert}"/>
                        </div>
                    </div>
                </td>
            </tr>
            `);

    this.Empty_inputs();
    this.Set_day_today();
    this.CalculateTotal();
    this.validate_payment_method_invoices();
    $(".hidden_pay").show();
    $(".disabled-pay").attr("disabled", true);
    $("#payment_method").modal("hide");
  },

  CalculateTotal: function () {
    let decimal_number = +$("#decimal").val();

    let tableBody = $("#pay_methods");
    let totalPayment = 0;

    if (tableBody) {
      tableBody.find("tr").each(function () {
        let paymentValue = parseFloat($(this).find("#payment").val());

        totalPayment += paymentValue;
      });
    }

    if (+$("#total_retention").val() > 0) {
      let total_retention = +$("#total_retention").val();
      totalPayment += total_retention;
    }

    $("#total_payment_l").text(totalPayment.toFixed(decimal_number));
    $("#total_payment").val(totalPayment.toFixed(decimal_number));

    if ($("#use_credit").is(":checked")) {
      this.CalculateUseCredit(false);
    }
    this.CalculateRemainingAmount();
  },

  CalculateRemainingAmount: function () {
    const decimal = +$("#decimal").val();
    const decimal_places_foreign = +$("#currency_foreign_id").val();
    const currency_foreign_rate = +$("#currency_foreign_rate").val();
    const amount_to_pay = +$("#amount_total_pay").val();
    const total_payment = +$("#total_payment").val();
    const remainingAmount = (amount_to_pay - total_payment).toFixed(decimal);
    const remainingAmountForeign = +(
      remainingAmount * currency_foreign_rate
    ).toFixed(decimal_places_foreign);
    if (remainingAmount < 0) {
      $("#remainingAmount").text((+0).toFixed(decimal));
      $("#remainingAmountForeign").text((0).toFixed(decimal_places_foreign));
    } else {
      $("#remainingAmount").text(remainingAmount);
      $("#remainingAmountForeign").text(remainingAmountForeign);
    }
  },

  CalculateIGTF: async function () {
    if ($("#igtf_pay").length) {
      if (
        $("#symbol-dairy").text() == "$" &&
        $("#requireReceipt").val() == "true" &&
        $("#amount_to_payment").val() != "" &&
        $("#required_igtf").val() == "true"
      ) {
        const amount = +$("#amount_to_payment").val();
        const valueIGTF = await jsonrpc(
          "/payments/get_value_igtf",
          
          {}
        );
        let { data, status } = valueIGTF;
        const is400 = status === 400;
        if (is400) return;
        let percentage = data / 100;
        let igtf = (amount * percentage).toFixed(+$("#decimal").val());
        $("#igtf_pay").val(igtf);
      } else {
        $("#igtf_pay").val("");
      }
    }
  },

  _onChangeSelectInvoice: function (ev) {
    const selectInvoice = ev.target;
    const decimal = +$("#decimal").val();
    const decimal_places_foreign = +$("#currency_foreign_id").val();
    const toPay = selectInvoice.closest("td").querySelector("#to_pay");
    const amount_residual = selectInvoice
      .closest("td")
      .querySelector("#amount_r");

    if (!selectInvoice.checked) {
      let amount_to_pay = +$("#amount_total_pay").val();
      let amount_select = amount_residual.value;
      amount_to_pay -= parseFloat(amount_select);
      console.log(amount_to_pay);
      $("#amount_total_pay").val(amount_to_pay.toFixed(decimal));
      $("#amount_total_l").text(amount_to_pay.toFixed(decimal));
      if (toPay) {
        toPay.style.display = "none";
        const amount_retention = selectInvoice
          .closest("td")
          .querySelector("#amount_retention");
        let retention = parseFloat(amount_retention.textContent);
        let total_retention = +$("#total_retention").val();
        total_retention -= retention;

        $("#total_retention").val(total_retention.toFixed(decimal));
        $("#total_retention_l").text(isNaN(total_retention) ? "0,00" : total_retention.toFixed(decimal));

        const amount_retention_vef = selectInvoice
          .closest("td")
          .querySelector("#amount_retention_vef");
        let retention_vef = parseFloat(amount_retention_vef.value);
        let total_retention_vef = +$("#total_retention_vef").val();
        total_retention_vef -= retention_vef;
        $("#total_retention_vef").val(
          total_retention_vef.toFixed(decimal_places_foreign)
        );
        $("#total_retention_l_vef").text(
          total_retention_vef
            .toFixed(decimal_places_foreign)
            .replace(".", ",")
        );

        if (+$("#total_retention").val() == 0) $(".hidden_retention").hide();
      }
      this.validate_payment_method_invoices();
      this.CalculateTotal();
      return;
    }

    let amount_to_pay = +$("#amount_total_pay").val();
    let amount_select = amount_residual.value;
    amount_to_pay += parseFloat(amount_select);
    $("#amount_total_pay").val(amount_to_pay.toFixed(decimal));
    $("#amount_total_l").text(amount_to_pay.toFixed(decimal));

    if (toPay) {
      toPay.style.display = "";
      $(".hidden_retention").show();
      const amount_retention = selectInvoice
        .closest("td")
        .querySelector("#amount_retention");
      let retention = parseFloat(amount_retention.textContent);
      let total_retention = +$("#total_retention").val();
      total_retention += retention;
      $("#total_retention").val(total_retention.toFixed(decimal));
      $("#total_retention_l").text(isNaN(total_retention) ? "0,00" : total_retention.toFixed(decimal));

      const amount_retention_vef = selectInvoice
        .closest("td")
        .querySelector("#amount_retention_vef");
      let retention_vef = parseFloat(amount_retention_vef.value);
      let total_retention_vef = +$("#total_retention_vef").val();
      total_retention_vef += retention_vef;
      $("#total_retention_vef").val(
        total_retention_vef.toFixed(decimal_places_foreign)
      );
      $("#total_retention_l_vef").text(
        total_retention_vef.toFixed(decimal_places_foreign).replace(".", ",")
      );
    }

    this.validate_payment_method_invoices();
    this.CalculateTotal();
  },

  _onClickDelete_payment: function (ev) {
    const amount_to_edit = ev.target;
    const $tr = $(amount_to_edit).closest("tr");
    const payment = $tr.find("#payment").val();
    let total_payment = +$("#total_payment").val();
    total_payment -= payment;
    let decimal_number = +$("#decimal").val();
    total_payment = total_payment.toFixed(decimal_number);
    $("#total_payment").val(total_payment);
    $("#total_payment_l").text(total_payment);
    ev.target.closest("tr").remove();
    this.CalculateTotal();

    let numTr = $("#pay_methods tr").length;
    if (numTr == 0) {
      $(".hidden_pay").hide();
      $("#total_payment_l").text("0");
      $("#total_payment").val(0);
      $(".disabled-input-pay").attr("disabled", true);
    }
  },

  _onClickEdit_payment: function (ev) {
    const amount_to_edit = ev.target;
    const $tr = $(amount_to_edit).closest("tr");
    const numTr = $tr.index();
    const payment =
      $tr.find("#payment_convert").val() !== ""
        ? $tr.find("#payment_convert").val()
        : $tr.find("#payment").val();
    const reference = $tr.find("#reference").val();
    const date_to_pay = $tr.find("#date_to_pay").val();
    const text_val = +$tr.find("#dairy_val").val();
    let symbolAfter = $tr.find("#symbolAfter").text();
    let symbolBefore = $tr.find("#symbolBefore").text();

    const symbolCurrency = symbolAfter + symbolBefore;

    $("#diary_pay").val(text_val);
    $("#amount_to_payment").val(payment);
    $("#reference_number").val(reference);
    $("#payday").val(date_to_pay);
    $("#pay_edit").val(numTr);
    $("#symbol-dairy").text(symbolCurrency);
    this.SetSymbolCurrencyInput();

    $(".disabled-pay").attr("disabled", false);
    $("#payment_method").modal("show");
    this.CalculateIGTF();
  },

  onClickUse_credit: function (ev) {
    this.CalculateUseCredit(true);
  },

  CalculateUseCredit: function (passPay) {
    let decimal_number = +$("#decimal").val();
    let balance = +$("#positive_balance").val();
    let total_amount = +$("#total_payment").val();
    if ($("#use_credit").is(":checked")) {
      total_amount += balance;
      $("#total_payment").val(total_amount.toFixed(decimal_number));
      $("#total_payment_l").text(total_amount.toFixed(decimal_number));
      $(".hidden_pay").show();
      $("#credit_apply").show();
      if (
        +$("#amount_to_pay").val() > 0 ||
        +$("#amount_to_pay").val() != ""
      ) {
        $(".disabled-input-pay").attr("disabled", false);
      }
    } else {
      $("#credit_apply").hide();
      if (passPay) {
        total_amount = (total_amount - balance).toFixed(decimal_number);
        $("#total_payment").val(total_amount);
        $("#total_payment_l").text(total_amount);
      }
      if (total_amount == 0) {
        $(".hidden_pay").hide();
        $(".disabled-input-pay").attr("disabled", true);
      }
    }
    this.CalculateRemainingAmount();
  },

  validate_payment_method_invoices: function () {
    let numTrpays = $("#pay_methods tr").length;
    let checkboxes = $("input[type='checkbox'].select_invoice");
    let selects_check = checkboxes.filter(":checked").length;
    if ($("#use_credit").is(":checked")) {
      $(".disabled-input-pay").attr("disabled", false);
    } else if (selects_check > 0 && numTrpays > 0) {
      $(".disabled-input-pay").attr("disabled", false);
    } else {
      $(".disabled-input-pay").attr("disabled", true);
    }
  },

  _onClickProcess_payment: async function (ev) {
    $("#process_payment").attr("disabled", true);
    const amountTotal = +$("#amount_total_pay").val();
    let notProof = false;

    if (amountTotal > 0) {
      let totalPay = +$("#total_payment").val();
      const paymentTotalPartial = await jsonrpc(
        "/payment_total_or_partial",
        
        {}
      );
      // const installmentPayments = await jsonrpc(
      //   "/installment_payments",
      //   
      //   {}
      // );
      let { data } = paymentTotalPartial;
      if (data == 1) {
        this.validateInputs(notProof);
      }
      if (data == 0) {
        if (amountTotal <= totalPay) {
          this.validateInputs(notProof);
          return;
        }
        this.errorValidation(notProof);
      }
    }
  },

  validateInputs: function (notProof) {
    if (!notProof) {
      if ($("#requireReceipt").val() == "false") {
        this.ProcessPayment();
        return;
      }

      if (
        $("#attach_input").val() != "" &&
        $("#requireReceipt").val() == "true"
      ) {
        this.ProcessPayment();
        return;
      }
      notProof = true;
    }
    this.errorValidation(notProof);
  },

  errorValidation: function (notProof) {
    let msg_error = notProof
      ? _t("Debe de agregar un comprobante antes de ser procesado el pago.")
      : _t(
          "El monto adeudado excede el monto registrado en los métodos de pago."
        );

    const error = `<div class="alert alert-danger" role="alert">
                              <h5 class="text-danger">${msg_error}</h5>
                          </div>`;
    $("#error_success_info").html(error);
    $("#error_success_in_pay").modal("show");

    $("#process_payment").attr("disabled", false);
  },

  ProcessPayment: async function () {
    let paysTr = $("#pay_methods tr");
    let invoiceSelected = $("#notes_invoices_results tr");

    const amountTotal = +$("#amount_total_pay").val();

    const {
      length: le,
      prevObject: prev,
      ...payments
    } = paysTr.map((_, payment) => {
      const paymentNode = payment.children[0].children[0];
      const idDairy = paymentNode.children[0].children[2].value;
      const reference = paymentNode.children[0].children[4].value;
      const dateToPay = paymentNode.children[0].children[5].value;
      let igtf_amount = 0;
      if (
        $("#requireReceipt").val() == "true" &&
        paymentNode.children[0].children[8]
      ) {
        igtf_amount = paymentNode.children[0].children[8].value;
      }

      const currencyId = paymentNode.children[1].children[0].value;
      let paymentAmount = paymentNode.children[1].children[2].value;
      const paymentConvert = paymentNode.children[1].children[5].value;

      if (paymentConvert != "") {
        paymentAmount = paymentConvert;
      }

      return {
        idDairy,
        reference,
        dateToPay,
        paymentAmount,
        currencyId,
        igtf_amount,
      };
    });
    // }

    const { length, prevObject, ...invoices } = invoiceSelected.map(
      (_, invoice) => {
        const invoiceNode = invoice.children[0].children[0];
        const invoiceSelect = invoiceNode.children[0].children[0];

        if (invoiceSelect.checked) {
          const idInvoice = invoiceNode.children[0].children[2].value;

          return {
            idInvoice,
          };
        }
        return;
      }
    );

    const useCredit = $("#use_credit").prop("checked");
    const dairy = +$("#diary").val();
    const partnerId = $("#clients").val();
    const attachId =
      $("#attach_id").val() == "0" ? false : $("#attach_id").val();

    const responsePayment = await jsonrpc(
      "/payments/register_payment",
      
      {
        use_credit: useCredit,
        dairy_type: dairy,
        amount_total: amountTotal,
        invoices: invoices,
        payments: payments,
        partner_id: partnerId,
        file: attachId,
      }
    );

    console.log(responsePayment);
    const { status, msg } = responsePayment;
    const is400 = status === 400;
    if (is400) {
      alert("Payment ERROR" + msg);
      $("#process_payment").attr("disabled", false);
      return;
    }

    const msg_success = _t("Los pagos han sido registrados exitosamente");
    const success = `<div class="alert alert-success" role="alert">
                              <h5 class="text-success">${msg_success}</h5>
                          </div>`;
    $("#error_success_info").html(success);
    $("#error_success_in_pay").modal("show");
    $("#diary").val("");
    $("#attach_id").val("");
    $("#attach_input").val("");
    $(".disabled-input-pay").attr("disabled", true);
    $(".hidden_retention").hide();
    this.fields_clear();

    return;
  },

  onChangeAttachment: function (ev) {
    $("#remove_attach").attr("disabled", false);
    var attachments = ev.target.files;
    for (let i = 0; i < attachments.length; i++) {
      var reader = new FileReader();
      reader.readAsDataURL(attachments[i]);
      reader.onload = async function (e) {
        await jsonrpc("/upload_attachment", {
            attachments: e.target.result,
            attachment_name: attachments[i].name,
          })
          .then(function (data) {
            const { data: dt, status } = data;
            const is400 = status === 400;
            if (is400) {
              $("#attach_input").val("");
              return;
            }
            $("#attach_id").val(dt);
          });
      };
    }
  },

  onClickRemoveAttach: async function (ev) {
    if ($("#attach_id").val() != "") {
      const attachId = $("#attach_id").val();
      const deleteAttach = await jsonrpc("/delete_attachment", {
        attach_id: attachId,
      });
      const { status } = deleteAttach;
      const is400 = status === 400;
      if (is400) return;
      $("#attach_input").val("");
      $("#attach_id").val("");
      $("#remove_attach").attr("disabled", true);
    }
  },
});

const selectedPartner = (partners, selected_partner) => {
  const copy = [...partners];
  const result = copy.filter(partner => partner.id === selected_partner);
  return result[0]; 
