odoo.define("binaural_mobile_multipackage.portal_budget_form", function (require) {
  "use strict";

  const publicWidget = require("web.public.widget");
  const portalBudgetForm = require("binaural_mobile.portal_budget_form");
  const ajax = require("web.ajax");
  const { _t } = require("web.core");

  // Note: This structure can be refactoriced deleting packagesByProduct variable to replace it for just use preLines variable.
  // To delete the method to add and verify by packagesByProduct.

  publicWidget.registry.portalBudgetForm = portalBudgetForm.extend({
    events: _.extend({}, portalBudgetForm.prototype.events, {
      "click .modal_btn_multiple_packaging": "onClickShowModalMultiplePackaging",
      "click .close-modal": "onClickCloseModal",
      "click #save-multipackage-btn": "onClickSaveMultiPackageBtn",
      "click #package-select-btn": "onClickPackageSelectBtn",
      "change .package-row-qty-input": "onChangePackageRowQtyInput",
    }),
    init: function (parent, options) {
      this._super.apply(this, arguments);
      this.orderState = "draft";
      this.modalPackagingOptions = [];
      this.modalPackagingSelected = [];
      this.packagesByProduct = [];
    },
    start: async function () {
      var def = await this._super.apply(this, arguments);

      return def;
    },

    _resetPackagesByProductInitialValues: function () {
      this.modalPackagingOptions = [];
      this.modalPackagingSelected = [];
      this.packagesByProduct = [];
    },


    // packageProduct
    _editPackageProduct: function (productId, productPackages) {
      productId = Number(productId);

      this.packagesByProduct = this.packagesByProduct.map(prPack => {
        if (prPack.productId === productId) {
          return {
            ...prPack,
            requestedPackages: productPackages,
          };
        }

        return prPack;
      });
    },

    // packageProduct
    _removePackageProduct: function (productId) {
      productId = Number(productId);

      this.packagesByProduct = this.packagesByProduct.filter(packOp => {
        return packOp.productId !== productId
      });
    },

    _addPackageProduct: function (productId, productPackages) {
      if (!productPackages.length) return;

      productId = Number(productId);

      this.packagesByProduct.push(
        {
          productId,
          requestedPackages: productPackages,
        }
      );

    },

    _setPackageByProduct: function (productId) {
      productId = Number(productId);

      if (!this.modalPackagingSelected.length) {
        this._removePackageProduct(productId);
        return;
      }

      const existPackagesByProduct = this._getPackageProduct(productId);

      if (existPackagesByProduct) {
        this._editPackageProduct(productId, this.modalPackagingSelected);
        return;
      }

      this._addPackageProduct(productId, this.modalPackagingSelected)
    },

    _setPackageByProductInitialValues: function (product) {
      const {id, packages} = product;

      const prevPackageProduct = this._getPackageProduct(id);

      this.modalPackagingSelected = prevPackageProduct ? prevPackageProduct.requestedPackages : [];

      this.modalPackagingOptions = packages.map(pack => ({
        qtyReq: 1, // quantity to request
        totalQtyReq: 1 * pack.qty, // total quantity requested 
        ...pack,
      }));
    },

    _setPackageSelect: function (productId, packageId, qtyReq) {
      const {qtyAvailable} = this._getProductById(productId);

      const targetPackage = this._getPackageOptionSelectedById(packageId);
      const newTargetPackage = this._getProductPackageWithQtyCalculated(qtyReq, targetPackage, qtyAvailable);

      this.modalPackagingSelected = this.modalPackagingSelected.map((packOpt) => {
        if (packOpt.id === newTargetPackage.id) {
          return {
            ...packOpt,
            ...newTargetPackage,
          }
        }

        return packOpt;

      });

      return targetPackage;
    },

    _addPackageOption: function (packageOption) {
      this.modalPackagingSelected.push(packageOption);
    },

    _removePackageOption: function (id) {
      id = Number(id);
      this.modalPackagingSelected = this.modalPackagingSelected.filter(packOp => {
        return packOp.id !== id
      });
    },

    // get
    _getPackageOptionSelectedById: function (id) {
      id = Number(id);
      return this.modalPackagingSelected.find(packOpt => packOpt.id === id);
    },

    _getPackageOptionById: function (id) {
      id = Number(id);
      return this.modalPackagingOptions.find(packOpt => packOpt.id === id);
    },

    _getPackageProduct: function (productId) {
      return this.packagesByProduct.find(prPack => prPack.productId === Number(productId));
    },

    _getProductById: function (id) {
      id = Number(id);
      return this.products.find( pr=> pr.id === id);
    },

    _getTotalQtyPackageSelected: function () {
      const sumTotalQtyReq = this.modalPackagingSelected.reduce(
        (accumulator, packSelected) => accumulator + packSelected.totalQtyReq,
        0,
      );

      return sumTotalQtyReq;
    },

    _getShowMultiPackageModalBtn: function (product) {
      const {packages, qtyAvailable, isPackaged} = product;

      if (!(this.settings.is_active_multi_packaging && packages.length > 1 && isPackaged) ) return;

      return qtyAvailable > 0 || this.settings.allow_out_of_stock_order;
    },

    _getProductPackageWithQtyCalculated: function (qtyReq, targetPackage, qtyAvailable) {
      const { qty: qtyPack } = targetPackage;
      
      if (qtyReq < 1) {
        targetPackage.qtyReq = 1;
        targetPackage.totalQtyReq = qtyPack;

        return targetPackage;
      }

      const allow_out_of_stock_order = this.settings.allow_out_of_stock_order;

      qtyReq =  Math.trunc(
        Number( qtyReq )
      );

      let totalQtyReq = qtyReq * qtyPack;

      if (totalQtyReq > qtyAvailable && !allow_out_of_stock_order) {
        qtyReq = Math.trunc(qtyAvailable / qtyPack);
        totalQtyReq = qtyReq * qtyPack;
      }

      targetPackage.qtyReq = qtyReq;
      targetPackage.totalQtyReq = totalQtyReq;

      return targetPackage;
    },

    // click
    onClickCloseModal: function (ev) {
      const modal = ev.target.closest(".modal");
      $(modal).modal("hide");
    },

    onClickPackageSelectBtn: function () {
      const modalElem = $("#multiple-packaging-modal");
      const product_id = modalElem.data("product-id");

      const packSelectElem = $("#package-select");
      const packOptionId = packSelectElem.val()

      const packOptionToSelect = this._getPackageOptionById(packOptionId);
      const existOptionSelected = this._getPackageOptionSelectedById(packOptionId);

      const {qtyAvailable} = this._getProductById(product_id);

      const existQtyAvailable = qtyAvailable > 0 || this.settings.allow_out_of_stock_order;

      if (existOptionSelected) {
        this._removePackageOption(packOptionId);
        this._renderPackageRows();
        return;
      }
      
      if (!packOptionToSelect || !existQtyAvailable) return;

      this._addPackageOption(packOptionToSelect);

      this._renderPackageRows();
    },

    _getIsValidSaveMultiPackage: function (totalQtyReq, productId) {
      if (totalQtyReq <= 0) return;

      const { qtyAvailable } = this._getProductById(productId);
      const forbidOutOfStockOrder = !this.settings.allow_out_of_stock_order;

      if (totalQtyReq > qtyAvailable && forbidOutOfStockOrder) {

        const warnError = `La cantidad total solicitada (${totalQtyReq}) es mayor a la disponible (${qtyAvailable}).`;

        this.showError(warnError);

        return false;
      }

      return true;

    },

    onClickSaveMultiPackageBtn: function (ev) {
      this._disableModalSaveBtn();

      const modalElem = $("#multiple-packaging-modal");
      const productId = Number(modalElem.data("product-id"));

      const labelTotalQtyElem = $(`#productItem${productId} .qty-product-label`);

      const modalProductItemElem = $(`#productItem${productId}`);

      const modalProductItemInputElem = modalProductItemElem.find("#qtyProduct");

      
      const totalQtyReq = this._getTotalQtyPackageSelected();
      const labelTotalQty = totalQtyReq || "Cant.";

      modalProductItemInputElem.val();

      const isValidSaveMultiPackage = this._getIsValidSaveMultiPackage(totalQtyReq, productId);

      if (!isValidSaveMultiPackage) return;
      
      modalProductItemInputElem.val(totalQtyReq);
      labelTotalQtyElem.text(labelTotalQty);
      
      this._setPackageByProduct(productId);
      
      this._disableModalSaveBtn(false);

      this._setProductPackageIntoPrelines();
      
      $(ev.target.closest(".modal")).modal("hide");
    },

    onClickShowModalMultiplePackaging: function (ev) {
      const tr = ev.target.closest("tr");
      const productId = tr.dataset.id;

      const targetProduct = this._getProductById(productId)

      if (!targetProduct) return;

      this._renderModalContent(targetProduct);

    },

    _onClickOpenProduct: async function () {
      this._resetPackagesByProductInitialValues();

      await this._super.apply(this, arguments);

    },

    _getPreLinesFromPackagesByProduct: function () {
      const newPreLines = [];

      this.packagesByProduct.forEach(packProduct => {
        const {productId, requestedPackages} = packProduct;

        const {listPrice} = this._getProductById(productId);

        const preLinePackages = requestedPackages.map( reqPack => {
          const {id, totalQtyReq} = reqPack;

          return {
            productId,
            packageId: id,
            qtyReq: totalQtyReq,
            priceUnit: listPrice,
          };
        })

        newPreLines.push(...preLinePackages);

      });

      return newPreLines;
    },


    _getPrelineIdxByPackageId: function (packageId) {
      const preLineIdx = this.preLines.findIndex(preLine => {
        return preLine.packageId === packageId;
      });

      return preLineIdx;
    },

    _setProductPackageIntoPrelines: function () {
      
      const packagePreLines = this._getPreLinesFromPackagesByProduct()

      for (const packPreLine of packagePreLines) {
        const prevPreLineIdx = this._getPrelineIdxByPackageId(packPreLine.packageId);

        // If not exist the line it'll be added
        if (prevPreLineIdx === -1) {
          this.preLines.push(packPreLine);
          continue;
        }

        // If exist the line it'll be overwritten
        this.preLines[prevPreLineIdx] = packPreLine;

      }

    },

    // change
    onChangePackageRowQtyInput: function (ev) {
      const modalElem = $("#multiple-packaging-modal");
      const productId = Number(modalElem.data("product-id"));
      const colInputQty = $(ev.target);
      const tr = $(ev.target.closest("tr"));
      
      const packageId = tr.data("package-id");
      const labelTotalQty = tr.find(".package-row-total-qty");
      
      const colInputValue = Number(colInputQty.val());

      const targetPackage = this._setPackageSelect(productId, packageId, colInputValue);

      const { qtyReq, totalQtyReq } = targetPackage;

      colInputQty.val(qtyReq);
      labelTotalQty.text(totalQtyReq);

    },

    // load


    // render
    _disableModalSaveBtn: function (disable = true) {
      $('#save_products').attr('disabled', disable)
    },

    _getRenderQtyOrderLine: function (order, line) {
      const { productUomQty, qtyAvailable, packages, uom, isProductPackaged } = line;
      const { state } = order;
      const { is_active_multi_packaging } = this.settings; 

      const isProductMultiPackage = packages.length > 1 && isProductPackaged && is_active_multi_packaging;
      const notIsProductMultiPackage = !isProductMultiPackage;
      const showInput = state === 'draft' && notIsProductMultiPackage;

      const packageQty = this._getDefaultUnitPackage(packages, isProductPackaged);
      let packagingQtyElem = packageQty > 1 && notIsProductMultiPackage ? `<label class="form-text" style="padding-right:3px;">Múltiplos de ${packageQty} </label>`: '';

      if (isProductMultiPackage && is_active_multi_packaging) {
        packagingQtyElem = '<label class="text-secondary form-text" style="padding-right:3px;">Se vende por empaquetados</label>';
      }

      const isPackaged = isProductPackaged ? 1 : 0;

      const uomElem = uom ? ` <label class="form-text" style="padding-right:3px;">${uom}</label>` : '';

      let inputElem = `
        <input 
          type="text"
          style="width: 60px; font-size: 15px;"
          class="form-control p-1 input_qty_line" 
          value="${productUomQty.toFixed(2)}"
          data-qty-available="${qtyAvailable}"
          data-qty-pack="${packageQty}"
          data-is-packaged="${isPackaged}"
        />
      `;

      const elem = `
          <div class="form-group">
              <label class="form-text" style="padding-right:3px;">Cantidad: </label>
              <label>
                ${inputElem}
              </label>
              ${uomElem}
              <br/>
              ${packagingQtyElem}
          </div>
      `;

      if (showInput) return elem;

      return `
        <div class="form-group">
            <label class="form-text" style="padding-right:3px;">
              Cantidad: ${productUomQty.toFixed(2)}
            </label>
            ${uomElem}
            <br/>
            ${packagingQtyElem}
        </div>
      `;
    },

    _renderGetQtyEntryElement: function (productResp) {
      const product = this._getProductFormatedFromResp(productResp);
      
      const {
        id,
        qtyAvailable,
      } = product;
      
      const preLine = this._getPreLineByProductId(id)
      const qtyInputValue = preLine ? preLine.qtyReq : '';

      const qtyLabel = _t("Cant.");

      const showMultiPackageModalBtn = this._getShowMultiPackageModalBtn(product)

      let qtyEntryElement = '';

      if (showMultiPackageModalBtn) {
        qtyEntryElement += `<label class="form-control form-text text-start qty-product-label" style="width: 80px !important;width: max-content;cursor:pointer;float: right;color: rgba(33, 37, 41, 0.7);">${qtyInputValue || "Cant."}</label>`;
        qtyEntryElement += '<label class="form-text text-end modal_btn_multiple_packaging bg-secondary text-white rounded p-1 px-1" style="font-weight: bolder;width: max-content;cursor:pointer;font-size: 12px;">Elegir empaquetados</label>'
        return qtyEntryElement;
      }


      qtyEntryElement += `<input type="text" class="form-control qty_product" id='qtyProduct' style="width: 80px;float: right;" data-qty-available="${qtyAvailable}" placeholder="${qtyLabel}" value="${qtyInputValue}"/>`;

      return qtyEntryElement;
    },

    _renderGetPackageSelectOption: function () {
      const optionElem = this.modalPackagingOptions.map(packaging_id => {
        const { id, name, qty} = packaging_id;

        return `
          <option value="${id}" class="text-capitalize">${name} (${qty})</option>
        `;
      });

      const placeholderOption = "<option selected=selected'>Elegir...</option>";

      optionElem.unshift(placeholderOption);

      return optionElem;
    },

    _renderPackageSelectOptions: function () {
      const packSelectElem = $("#package-select");

      packSelectElem.empty();

      const optionsElem = this._renderGetPackageSelectOption();

      packSelectElem.append(optionsElem);
      
    },

    _renderGetPackageRows: function () {

      const packsSelected = this.modalPackagingSelected;

      if (!packsSelected.length) {
        return `
          <p class="m-0 pb-0 pt-4">Sin Empaquetados</p>
        `;
      }

      const rows = packsSelected.map(packSelected => {
        const { id, name, totalQtyReq, qtyReq } = packSelected;
        const showInput = this.orderState === "draft";

        const inputElem = showInput ? `
          <input style='width:50px;text-align: center;' class='package-row-qty-input' value="${qtyReq}" />
        `: '';

        return `
          <tr data-package-id=${id}>
            <td class="text-capitalize">${name}</td>
            <td class="text-center">
            ${inputElem}
            </td>
            <td class="text-center package-row-total-qty">${totalQtyReq}</td>
          </tr>
        `;
      });

      return rows;
    },

    _renderPackageRows: function () {
      const bodyElem = $("#multiple-packaging-modal #body");

      $("#multiple-packaging-modal #body").empty();

      const packageRowsHtml = this._renderGetPackageRows();

      bodyElem.append(packageRowsHtml);
    },

    _renderModalContent: function (targetProduct) {

      const modalElem = $("#multiple-packaging-modal");
      const titleElem = $("#multiple-packaging-modal #product-name");

      const {id, name} = targetProduct;

      modalElem.modal("show");
      modalElem.data("product-id", id)
      
      titleElem.text(name);
      
      this._setPackageByProductInitialValues(targetProduct);
      
      this._renderPackageSelectOptions();
      
      this._renderPackageRows();

    },

    _appendProduct: async (
      self,
      products,
      allow_out_of_stock_order,
      stock_packaging,
      tbody
    ) => {
      if (!products) return;

      // tbody.empty()
      let priceLabel = _t("Precio");
      const symbol = $("#symbolB").val();
      let symbolAfter = "";
      let symbolBefore = "";
      let decimalPlaces = +$("#decimal").val();
      
      if ($("#positionS").val() == "after") {
        symbolAfter = symbol;
      } else {
        symbolBefore = symbol;
      }
      
      let dont_show_quantity_available = false;
      try {
        dont_show_quantity_available = await self._rpc({
          model: "res.users",
          method: "has_group",
          args: ["binaural_mobile.group_sellers_show_quantity_available"],
        });
      } catch (e) {}
      
      products.forEach((product) => {
        let {
          display_name,
          list_price,
          image,
          quantity,
          id,
          msg_price,
          uom_id,
          type,
          packaged_product,
          packaging_ids,
        } = product;
        let packFactorLabel = ``;
        let displayQtyOrType = "";

        if (!dont_show_quantity_available) {
          if (quantity == 0 && !allow_out_of_stock_order && type != "product") {
            displayQtyOrType = type;
          } else {
            displayQtyOrType = quantity.toFixed(2) + " " + uom_id[1];
          }
        }

        let hasPackageFactorValid = self.settings.is_active_multi_packaging ? packaging_ids.length === 1 : packaging_ids.length > 0
        hasPackageFactorValid = stock_packaging && hasPackageFactorValid && packaged_product;

        if (hasPackageFactorValid) {
          const packagingQty = self._getDefaultUnitPackage(packaging_ids, packaged_product);
          packFactorLabel = packaged_product ? `<label class="form-text" style="min-width: max-content;">Solo múltiplos de ${packagingQty}</label><input type='hidden' id='product_qty_pack' value='${packagingQty}'/><br/>`: ``;
        }

        if (type != "product") {
          quantity = 999;
        }

        list_price = list_price.toFixed(decimalPlaces);

        const qtyEntryElement = self._renderGetQtyEntryElement(product);

        tbody.append(`
          <tr class="productItem" data-id="${id}" id="productItem${id}">
              <td class="text-center"><img style="width: auto; height:70px;" src="${image}"/></td>
              <td colspan="2">
                <label style="font-weight: bolder; font-size: 15px;" class="name_product">${display_name}</label><br/>
                <input type="hidden" class="val_product" value="${id}"/>
                <label class="form-text">${priceLabel}:</label>
                <label class="form-text price_product" style="font-weight: bolder;">${symbolBefore} ${list_price} ${symbolAfter}</label><br/>
                <label class="form-text" style="font-weight: bolder;">${
                  displayQtyOrType || ""
                }</label><input type='hidden' id="qtyAvailable" value='${quantity}'/>
              </td>
              <td style="width: 150px;text-align: end;">
                <label>
                  ${qtyEntryElement}
                </label>
                ${packFactorLabel}
                <label class="form-text text-success">${msg_price || ""}</label>
              </td>
          </tr>
        `);
      });
    },

    _renderNoteBeforeProductTable: function () {

      const noteElem = $("#product-table-note")

      let msgNote = '';

      if (this.settings.is_active_multi_packaging && this.orderState === "draft") {
        msgNote = 'Nota: Los productos que "Se venden por empaquetados" deben eliminarse y añadirse nuevamente.'
        noteElem.text(msgNote);
        return;
      };

    },

    build_table_products: async function(data, buildTax) {
      await this._super.apply(this, arguments);

      const {state} = data[0];

      this.orderState = state;

      this._renderNoteBeforeProductTable();

    },
  });
});
