odoo.define("binaural_iot_mf.action_mf", function(require) {

  var IoTLongpolling = require('iot.IoTLongpolling')
  var core = require('web.core');
  var Widget = require('web.Widget');
  var widget_registry = require('web.widget_registry');
  var IoTConnectionMixin = require('iot.mixins').IoTConnectionMixin;
  var DeviceProxy = require('iot.DeviceProxy');
  var IoTLongpolling = require("iot.IoTLongpolling")
  var rpc = require('web.rpc');
  var session = require('web.session');

  var _t = core._t;

  function get_device_info_by_id(self, id) {
    if (!id) {
      self.device = false
      return;
    }
    rpc.query({
      model: 'iot.device',
      method: 'search_read',
      domain: [['id', '=', id], ['connected', '=', true]],
    }).then(function(iot_device) {
      if (iot_device.length > 0) {
        self.device = iot_device[0]
      }
      else {
        self.device = false
      }
    }).catch(function(err) {
      self.device = false
    })
  }

  //----------------------------------------------------------------------------
  //                            GET SERIAL MACHINE
  //----------------------------------------------------------------------------

  var getSerialFiscalMachine = Widget.extend(IoTConnectionMixin, {
    tagName: 'button',
    className: 'btn btn-primary',
    events: { 'click': '_action_button' },
    init: function(parent, params) {
      get_device_info_by_id(this, params.res_id || false)
      return this._super.apply(this, arguments);
    },
    start: function() {
      this._super.apply(this, arguments);
      this.$el.text(_t('GET SERIAL FISCAL MACHINE'));
    },
    _action_button: function(ev) {
      if (!this.device) {
        return this.do_warn(_t('No device connected'));
      }
      this.iot_device = new DeviceProxy(this, {
        identifier: this.device.identifier,
        iot_ip: this.device.iot_ip,
      });
      var fdm = this.iot_device;
      const promise = new Promise(async (resolve, reject) => {
        fdm.add_listener(data => {
          fdm.remove_listener();
          resolve(data["value"]);
        });
        await fdm.action({
          action: "get_last_invoice_number",
          data: { "me": "you" },
        });
      });
      promise
        .then(data => {
          if (data.valid) {
            rpc.query({
              model: 'iot.device',
              method: 'set_serial_machine',
              args: [this.device.id, data],
            })
              .then(function() {
                window.location.reload()
              })
          }
        })
    },
  });

  widget_registry.add('get_fiscal_serial', getSerialFiscalMachine);

  //----------------------------------------------------------------------------
  //                           CREATE INVOICE 
  //----------------------------------------------------------------------------

  var createInvoice = Widget.extend(IoTConnectionMixin, {
    tagName: 'button',
    className: 'btn btn-primary',
    events: { 'click': '_action_button' },
    init: function(parent, params) {
      if (params.data.iot_mf) {
        get_device_info_by_id(this, params.data.iot_mf.data.id || false)
      }
      this.data = params
      return this._super.apply(this, arguments);
    },
    start: function() {
      this._super.apply(this, arguments);
      this.$el.text(_t('PRINT INVOICE FISCAL MACHINE'));
    },
    _action_button: async function(ev) {
      if (!this.device) {
        return this.do_warn(_t('No device connected'));
      }
      this.iot_device = new DeviceProxy(this, {
        identifier: this.device.identifier,
        iot_ip: this.device.iot_ip,
      });

      const request = await rpc.query({
        model: 'account.move',
        method: 'check_print_out_invoice',
        args: [this.data.res_id],
      })

      var fdm = this.iot_device;
      const promise = new Promise(async (resolve, reject) => {
        fdm.add_listener(data => {
          fdm.remove_listener();
          resolve(data["value"]);
        });
        await fdm.action({
          action: "print_out_invoice",
          data: request,
        });
      });
      promise
        .then(data => {
          if (data.valid) {
            rpc.query({
              model: 'account.move',
              method: 'print_out_invoice',
              args: [this.data.res_id, data],
            })
              .then(function() {
                window.location.reload()
              })
          }
        })
    },
  });

  widget_registry.add('print_out_invoice', createInvoice);

  //----------------------------------------------------------------------------
  //                           CREATE REFUND 
  //----------------------------------------------------------------------------

  var createRefund = Widget.extend(IoTConnectionMixin, {
    tagName: 'button',
    className: 'btn btn-primary',
    events: { 'click': '_action_button' },
    init: function(parent, params) {
      if (params.data.iot_mf) {
        get_device_info_by_id(this, params.data.iot_mf.data.id || false)
      }
      this.data = params
      return this._super.apply(this, arguments);
    },
    start: function() {
      this._super.apply(this, arguments);
      this.$el.text(_t('PRINT REFUND FISCAL MACHINE'));
    },
    _action_button: async function(ev) {
      if (!this.device) {
        return this.do_warn(_t('No device connected'));
      }
      this.iot_device = new DeviceProxy(this, {
        identifier: this.device.identifier,
        iot_ip: this.device.iot_ip,
      });

      const request = await rpc.query({
        model: 'account.move',
        method: 'check_print_out_refund',
        args: [this.data.res_id],
      })

      var fdm = this.iot_device;
      const promise = new Promise(async (resolve, reject) => {
        fdm.add_listener(data => {
          fdm.remove_listener();
          resolve(data["value"]);
        });
        await fdm.action({
          action: "print_out_refund",
          data: request,
        });
      });
      promise
        .then(data => {
          if (data.valid) {
            rpc.query({
              model: 'account.move',
              method: 'print_out_refund',
              args: [this.data.res_id, data],
            })
              .then(function() {
                window.location.reload()
              })
          }
        })
    },
  });

  widget_registry.add('print_out_refund', createRefund);

  //----------------------------------------------------------------------------
  //                           REPRINT DOCUMENT 
  //----------------------------------------------------------------------------

  var reprintDocument = Widget.extend(IoTConnectionMixin, {
    tagName: 'button',
    className: 'btn btn-primary',
    events: { 'click': '_action_button' },
    init: function(parent, params) {
      if (params.data.iot_mf) {
        get_device_info_by_id(this, params.data.iot_mf.data.id || false)
      }
      this.data = params
      return this._super.apply(this, arguments);
    },
    start: function() {
      this._super.apply(this, arguments);
      this.$el.text(_t('REPRINT DOCUMENT'));
    },
    _action_button: async function(ev) {
      if (!this.device) {
        return this.do_warn(_t('No device connected'));
      }
      this.iot_device = new DeviceProxy(this, {
        identifier: this.device.identifier,
        iot_ip: this.device.iot_ip,
      });

      const request = await rpc.query({
        model: 'account.move',
        method: 'check_reprint',
        args: [this.data.res_id],
      })

      var fdm = this.iot_device;
      new Promise(async (resolve, reject) => {
        fdm.add_listener(data => {
          fdm.remove_listener();
          resolve(data["value"]);
        });
        await fdm.action({
          action: "reprint",
          data: request,
        });
      });
    },
  });

  widget_registry.add('reprint', reprintDocument);

  //----------------------------------------------------------------------------
  //                           REPORT Z 
  //----------------------------------------------------------------------------

  var reportZ = Widget.extend(IoTConnectionMixin, {
    tagName: 'button',
    className: 'btn btn-primary',
    events: { 'click': '_action_button' },
    init: function(parent, params) {
      if (params.model === "iot.device") {
        this.device = params.data
      } else {
        if (params.data.iot_mf) {
          get_device_info_by_id(this, params.data.iot_mf.data.id || false)
        }
      }
      this.model_action = params.model
      this.data = params
      return this._super.apply(this, arguments);
    },
    start: function() {
      this._super.apply(this, arguments);
      this.$el.text(_t('REPORT Z'));
    },
    _action_button: async function(ev, data) {
      if (!this.device) {
        return this.do_warn(_t('No device connected'));
      }
      this.iot_device = new DeviceProxy(this, {
        identifier: this.device.identifier,
        iot_ip: this.device.iot_ip,
      });

      const request = await rpc.query({

        model: 'account.move',
        method: 'check_report_z',
        args: [[], this.device.serial_machine],
      })

      var fdm = this.iot_device;

      const promise = new Promise(async (resolve, reject) => {
        fdm.add_listener(data => {
          fdm.remove_listener();
          resolve(data["value"]);
        });
        await fdm.action({
          action: "report_z",
          data: { "data": "to" },
        });
        promise
          .then(data => {
            if (data.valid) {
              rpc.query({
                model: 'account.move',
                method: 'report_z',
                args: [[], this.device.serial_machine, data],
              })
              if (this.model_action == 'pos.session') {
                rpc.query({
                  model: 'pos.session',
                  method: 'set_report_z',
                  args: [this.data.res_id, data],
                })
                  .then(function() {
                    window.location.reload()
                  })
              }
            }
          })
      });
    },
  });

  widget_registry.add('generate_report_z', reportZ);

  var reportX = Widget.extend(IoTConnectionMixin, {
    tagName: 'button',
    className: 'btn btn-primary',
    events: { 'click': '_action_button' },
    init: function(parent, params) {
      if (params.model === "iot.device") {
        this.device = params.data
      } else {
        if (params.data.iot_mf) {
          get_device_info_by_id(this, params.data.iot_mf.data.id || false)
        }
      }
      this.model_action = params.model
      this.data = params
      return this._super.apply(this, arguments);
    },
    start: function() {
      this._super.apply(this, arguments);
      this.$el.text(_t('REPORT X'));
    },
    _action_button: async function(ev, data) {
      if (!this.device) {
        return this.do_warn(_t('No device connected'));
      }
      this.iot_device = new DeviceProxy(this, {
        identifier: this.device.identifier,
        iot_ip: this.device.iot_ip,
      });

      var fdm = this.iot_device;

      new Promise(async (resolve, reject) => {
        fdm.add_listener(data => {
          fdm.remove_listener();
          resolve(data["value"]);
        });
        await fdm.action({
          action: "report_x",
          data: { "data": "to" },
        });
      });
    },
  });

  widget_registry.add('generate_report_x', reportX);

  var programacion = Widget.extend(IoTConnectionMixin, {
    tagName: 'button',
    className: 'btn btn-primary',
    events: { 'click': '_action_button' },
    init: function(parent, params) {
      if (params.model === "iot.device") {
        this.device = params.data
      } else {
        if (params.data.iot_mf) {
          get_device_info_by_id(this, params.data.iot_mf.data.id || false)
        }
      }
      this.model_action = params.model
      this.data = params
      return this._super.apply(this, arguments);
    },
    start: function() {
      this._super.apply(this, arguments);
      this.$el.text(_t('PROGRAMACION'));
    },
    _action_button: async function(ev, data) {
      if (!this.device) {
        return this.do_warn(_t('No device connected'));
      }
      this.iot_device = new DeviceProxy(this, {
        identifier: this.device.identifier,
        iot_ip: this.device.iot_ip,
      });

      var fdm = this.iot_device;

      new Promise(async (resolve, reject) => {
        fdm.add_listener(data => {
          fdm.remove_listener();
          resolve(data["value"]);
        });
        await fdm.action({
          action: "programacion",
          data: { "data": "to" },
        });
      });
    },
  });

  widget_registry.add('programacion', programacion);

  var statusMachine = Widget.extend(IoTConnectionMixin, {
    tagName: 'button',
    className: 'btn btn-primary',
    events: { 'click': '_action_button' },
    init: function(parent, params) {
      if (params.model === "iot.device") {
        this.device = params.data
      } else {
        if (params.data.iot_mf) {
          get_device_info_by_id(this, params.data.iot_mf.data.id || false)
        }
      }
      this.model_action = params.model
      this.data = params
      return this._super.apply(this, arguments);
    },
    start: function() {
      this._super.apply(this, arguments);
      this.$el.text(_t('STATUS'));
    },
    _action_button: async function(ev, data) {
      if (!this.device) {
        return this.do_warn(_t('No device connected'));
      }
      this.iot_device = new DeviceProxy(this, {
        identifier: this.device.identifier,
        iot_ip: this.device.iot_ip,
      });

      var fdm = this.iot_device;
      self = this

      const promise = new Promise(async (resolve, reject) => {
        fdm.add_listener(data => {
          fdm.remove_listener();
          resolve(data["value"]);
        });
        await fdm.action({
          action: "status",
        });
      });
      promise.then(data => {
        this.do_notify(data.message)
      })
    },
  });

  widget_registry.add('statusMachine', statusMachine);

  var status1 = Widget.extend(IoTConnectionMixin, {
    tagName: 'button',
    className: 'btn btn-primary',
    events: { 'click': '_action_button' },
    init: function(parent, params) {
      if (params.model === "iot.device") {
        this.device = params.data
      } else {
        if (params.data.iot_mf) {
          get_device_info_by_id(this, params.data.iot_mf.data.id || false)
        }
      }
      this.model_action = params.model
      this.data = params
      return this._super.apply(this, arguments);
    },
    start: function() {
      this._super.apply(this, arguments);
      this.$el.text(_t('STATUS 1'));
    },
    _action_button: async function(ev, data) {
      if (!this.device) {
        return this.do_warn(_t('No device connected'));
      }
      this.iot_device = new DeviceProxy(this, {
        identifier: this.device.identifier,
        iot_ip: this.device.iot_ip,
      });

      var fdm = this.iot_device;
      self = this

      const promise = new Promise(async (resolve, reject) => {
        fdm.add_listener(data => {
          fdm.remove_listener();
          resolve(data["value"]);
        });
        await fdm.action({
          action: "status1",
          data: { "data": "to" },
        });
      });
      promise.then(data => {
        let newdata = data.data;
        let claves = Object.keys(newdata);
        for (let i = 0; i < claves.length; i++) {
          let clave = claves[i];
          this.do_notify(`<p><b>${clave}:</b> ${newdata[clave]}</p>`)
        }
      })
    },
  });

  widget_registry.add('status1', status1);
})
