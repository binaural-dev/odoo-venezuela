/** @odoo-module **/

import BarcodePickingModel from '@stock_barcode/models/barcode_picking_model';
import { _t } from 'web.core';

export default class BinauralBarcodePickingModel extends BarcodePickingModel {
  constructor(params) {
    super(...arguments);
  }

  _lineIsNotComplete(line) {
    if (line.fake_line) {
      return true
    }
    return super._lineIsNotComplete(line);
  }
  _sortLine(lines) {
    return lines.sort((l1, l2) => {
      return l1.priority_location > l2.priority_location ? 1 : -1;
    });
  }
  _createLinesState() {
    const picking = this.cache.getRecord(this.params.model, this.params.id);
    let res = super._createLinesState();
    let products = res.map((line) => line.product_id.id)
    for (const id of picking.move_ids) {
      let smlData = this.cache.getRecord('stock.move', id);
      let base = {
        "location_id": {},
        "qty_done": 0,
        "owner_id": false,
        "lot_id": false,
        "lot_name": false,
        "package_id": false,
        "result_package_id": false,
        "dummy_id": "",
        "product_packaging_id": false,
        "product_packaging_uom_qty": 0,
        "move_id": 81,
        "priority_location": 9999,
        "demanded_qty": 1,
        "fake_line": false,
      }
      if (!products.includes(smlData.product_id)) {
        smlData.id = id;
        smlData.product_id = this.cache.getRecord('product.product', smlData.product_id);
        smlData.location_id = this.cache.getRecord('stock.location', smlData.location_id);
        smlData.product_uom_id = this.cache.getRecord('uom.uom', smlData.product_uom);
        smlData.fake_line = true;
        smlData.qty_done = 0;
        smlData.virtual_id = id;
        let newLine = Object.assign(base, smlData)
        res.push(newLine);
      }
    }

    for (const line of res) {
      if (!line.fake_line) {
        line.fake_line = false;
      }
    }
    return res
  }

  async _processBarcode(barcode) {
    let barcodeData = {};
    let currentLine = false;
    // Creates a filter if needed, which can help to get the right record
    // when multiple records have the same model and barcode.
    const filters = {};
    if (this.selectedLine && this.selectedLine.product_id.tracking !== 'none') {
      filters['stock.lot'] = {
        product_id: this.selectedLine.product_id.id,
      };
    }
    try {
      barcodeData = await this._parseBarcode(barcode, filters);
      if (!barcodeData.match && filters['stock.lot'] &&
        !this.canCreateNewLot && this.useExistingLots) {
        // Retry to parse the barcode without filters in case it matches an existing
        // record that can't be found because of the filters
        const lot = await this.cache.getRecordByBarcode(barcode, 'stock.lot');
        if (lot) {
          Object.assign(barcodeData, { lot, match: true });
        }
      }
    } catch (parseErrorMessage) {
      barcodeData.error = parseErrorMessage;
    }

    // Process each data in order, starting with non-ambiguous data type.
    if (barcodeData.action) { // As action is always a single data, call it and do nothing else.
      return await barcodeData.action();
    }
    // Depending of the configuration, the user can be forced to scan a specific barcode type.
    const check = this._checkBarcode(barcodeData);
    if (check.error) {
      return this.notification.add(check.message, { title: check.title, type: "danger" });
    }

    if (barcodeData.packaging) {
      barcodeData.product = this.cache.getRecord('product.product', barcodeData.packaging.product_id);
      barcodeData.quantity = ("quantity" in barcodeData ? barcodeData.quantity : 1) * barcodeData.packaging.qty;
      barcodeData.uom = this.cache.getRecord('uom.uom', barcodeData.product.uom_id);
    }

    if (barcodeData.product) { // Remembers the product if a (packaging) product was scanned.
      this.lastScanned.product = barcodeData.product;
    }

    if (barcodeData.lot && !barcodeData.product) {
      barcodeData.product = this.cache.getRecord('product.product', barcodeData.lot.product_id);
    }

    await this._processLocation(barcodeData);
    await this._processPackage(barcodeData);
    if (barcodeData.stopped) {
      // TODO: Sometime we want to stop here instead of keeping doing thing,
      // but it's a little hacky, it could be better to don't have to do that.
      return;
    }

    if (barcodeData.weight) { // Convert the weight into quantity.
      barcodeData.quantity = barcodeData.weight.value;
    }

    // If no product found, take the one from last scanned line if possible.
    if (!barcodeData.product) {
      if (barcodeData.quantity) {
        currentLine = this.selectedLine || this.lastScannedLine;
      } else if (this.selectedLine && this.selectedLine.product_id.tracking !== 'none') {
        currentLine = this.selectedLine;
      } else if (this.lastScannedLine && this.lastScannedLine.product_id.tracking !== 'none') {
        currentLine = this.lastScannedLine;
      }
      if (currentLine) { // If we can, get the product from the previous line.
        const previousProduct = currentLine.product_id;
        // If the current product is tracked and the barcode doesn't fit
        // anything else, we assume it's a new lot/serial number.
        if (previousProduct.tracking !== 'none' &&
          !barcodeData.match && this.canCreateNewLot) {
          barcodeData.lotName = barcode;
          barcodeData.product = previousProduct;
        }
        if (barcodeData.lot || barcodeData.lotName ||
          barcodeData.quantity) {
          barcodeData.product = previousProduct;
        }
      }
    }
    const { product } = barcodeData;
    if (!product) { // Product is mandatory, if no product, raises a warning.
      if (!barcodeData.error) {
        if (this.groups.group_tracking_lot) {
          barcodeData.error = _t("You are expected to scan one or more products or a package available at the picking location");
        } else {
          barcodeData.error = _t("You are expected to scan one or more products.");
        }
      }
      return this.notification.add(barcodeData.error, { type: 'danger' });
    } else if (barcodeData.lot && barcodeData.lot.product_id !== product.id) {
      delete barcodeData.lot; // The product was scanned alongside another product's lot.
    }
    if (barcodeData.weight) { // the encoded weight is based on the product's UoM
      barcodeData.uom = this.cache.getRecord('uom.uom', product.uom_id);
    }

    // Searches and selects a line if needed.
    if (!currentLine || this._shouldSearchForAnotherLine(currentLine, barcodeData)) {
      currentLine = this._findLine(barcodeData);
    }

    // Default quantity set to 1 by default if the product is untracked or
    // if there is a scanned tracking number.
    if (product.tracking === 'none' || barcodeData.lot || barcodeData.lotName || this._incrementTrackedLine()) {
      const hasUnassignedQty = currentLine && currentLine.qty_done && !currentLine.lot_id && !currentLine.lot_name;
      const isTrackingNumber = barcodeData.lot || barcodeData.lotName;
      const defaultQuantity = isTrackingNumber && hasUnassignedQty ? 0 : 1;
      barcodeData.quantity = barcodeData.quantity || defaultQuantity;
      if (product.tracking === 'serial' && barcodeData.quantity > 1 && (barcodeData.lot || barcodeData.lotName)) {
        barcodeData.quantity = 1;
        this.notification.add(
          _t(`A product tracked by serial numbers can't have multiple quantities for the same serial number.`),
          { type: 'danger' }
        );
      }
    }

    if ((barcodeData.lotName || barcodeData.lot) && product) {
      const lotName = barcodeData.lotName || barcodeData.lot.name;
      for (const line of this.currentState.lines) {
        if (line.product_id.tracking === 'serial' && this.getQtyDone(line) !== 0 &&
          ((line.lot_id && line.lot_id.name) || line.lot_name) === lotName) {
          return this.notification.add(
            _t("The scanned serial number is already used."),
            { type: 'danger' }
          );
        }
      }
      // Prefills `owner_id` and `package_id` if possible.
      const prefilledOwner = (!currentLine || (currentLine && !currentLine.owner_id)) && this.groups.group_tracking_owner && !barcodeData.owner;
      const prefilledPackage = (!currentLine || (currentLine && !currentLine.package_id)) && this.groups.group_tracking_lot && !barcodeData.package;
      if (this.useExistingLots && (prefilledOwner || prefilledPackage)) {
        const lotId = (barcodeData.lot && barcodeData.lot.id) || (currentLine && currentLine.lot_id && currentLine.lot_id.id) || false;
        const res = await this.orm.call(
          'product.product',
          'prefilled_owner_package_stock_barcode',
          [product.id],
          {
            lot_id: lotId,
            lot_name: (!lotId && barcodeData.lotName) || false,
          }
        );
        this.cache.setCache(res.records);
        if (prefilledPackage && res.quant && res.quant.package_id) {
          barcodeData.package = this.cache.getRecord('stock.quant.package', res.quant.package_id);
        }
        if (prefilledOwner && res.quant && res.quant.owner_id) {
          barcodeData.owner = this.cache.getRecord('res.partner', res.quant.owner_id);
        }
      }
    }

    // Updates or creates a line based on barcode data.
    if (currentLine) { // If line found, can it be incremented ?
      if (currentLine.fake_line) {
        return this.notification.add(
          _t("The product you are trying to scan does not have reserved quantities"),
          { type: 'danger' }
        );
      }
      if (this.record.picking_type_id.type_steps == "pick") {
        let remainingQtyTemp = currentLine.reserved_uom_qty - currentLine.qty_done;
        barcodeData.quantity = remainingQtyTemp || 1;
      }
      let exceedingQuantity = 0;
      if (product.tracking !== 'serial' && barcodeData.uom && barcodeData.uom.category_id == currentLine.product_uom_id.category_id) {
        // convert to current line's uom
        barcodeData.quantity = (barcodeData.quantity / barcodeData.uom.factor) * currentLine.product_uom_id.factor;
        barcodeData.uom = currentLine.product_uom_id;
      }
      // Checks the quantity doesn't exceed the line's remaining quantity.
      if (currentLine.reserved_uom_qty && product.tracking === 'none') {
        const remainingQty = currentLine.reserved_uom_qty - currentLine.qty_done;
        if (barcodeData.quantity > remainingQty) {
          // In this case, lowers the increment quantity and keeps
          // the excess quantity to create a new line.
          exceedingQuantity = barcodeData.quantity - remainingQty;
          barcodeData.quantity = remainingQty;
        }
      }
      if (barcodeData.quantity > 0 || barcodeData.lot || barcodeData.lotName) {
        const fieldsParams = this._convertDataToFieldsParams(barcodeData);
        if (barcodeData.uom) {
          fieldsParams.uom = barcodeData.uom;
        }
        await this.updateLine(currentLine, fieldsParams);
      }
      if (exceedingQuantity) { // Creates a new line for the excess quantity.
        if (this.config.restrict_add_exceeding_quantity) {

          return this.notification.add(
            _t("You cannot add more products than the limit"),
            { type: 'danger' }
          );
        }
        barcodeData.quantity = exceedingQuantity;
        const fieldsParams = this._convertDataToFieldsParams(barcodeData);
        if (barcodeData.uom) {
          fieldsParams.uom = barcodeData.uom;
        }
        currentLine = await this._createNewLine({
          copyOf: currentLine,
          fieldsParams,
        });
      }
    } else { // No line found, so creates a new one.
      if (this.config.restrict_add_exceeding_quantity) {
        return this.notification.add(
          _t("You cannot add more products than the limit"),
          { type: 'danger' }
        );

      }
      const fieldsParams = this._convertDataToFieldsParams(barcodeData);
      if (barcodeData.uom) {
        fieldsParams.uom = barcodeData.uom;
      }
      currentLine = await this.createNewLine({ fieldsParams });
    }

    // And finally, if the scanned barcode modified a line, selects this line.
    if (currentLine) {
      this._selectLine(currentLine);
    }
    this.trigger('update');
  }

  displaySupervisorCheck() {
    this.view = 'supervisorCheck';
    this.trigger('update');
  }
}
