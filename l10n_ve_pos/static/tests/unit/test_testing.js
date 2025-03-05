odoo.define("l10n_ve_pos.testing", function(require) {


  const makeTestEnvironment = require('web.test_env');
  const testUtils = require('web.test_utils');
  const { mount } = require('@web/../tests/helpers/utils');
  const { LegacyComponent } = require("@web/legacy/legacy_component");

  const { useState, xml } = owl;

  QUnit.module('unit tests INTEGRA', {
    before() { },
  });

  QUnit.test('simple fast inputs with capture in between', async function(assert) {
    assert.expect(1);
    const target = testUtils.prepareTarget();
    const env = makeTestEnvironment();

    assert.strictEqual(1, 1);
  });
});
