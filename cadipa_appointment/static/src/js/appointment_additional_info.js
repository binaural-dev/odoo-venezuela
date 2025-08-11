/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";
console.log('cadipaAdditionalInfo loaded');

publicWidget.registry.cadipaAdditionalInfo = publicWidget.Widget.extend({
  selector: '.cadipa-additional-info',
  events: {
    'change .cadipa-country': '_onCountryChange',
    'change .cadipa-state': '_onStateChange',
    'change #city_id': '_onCityChange',
    'change .cadipa-municipality': '_onMunicipalityChange',
    'input .cadipa-zip': '_onZipInput',          // <-- solo números
  },

  async start() {
    const res = await this._super(...arguments);

    // cache
    this.$country = this.$('.cadipa-country');
    this.$state = this.$('.cadipa-state');
    this.$city = this.$('#city_id');
    this.$municipality = this.$('.cadipa-municipality');
    this.$parish = this.$('.cadipa-parish');
    this.$zip = this.$('.cadipa-zip');

    this.$wrapState = this.$('#wrap_state');
    this.$wrapCity = this.$('#wrap_city');
    this.$wrapZip = this.$('#wrap_zip');         // <-- wrapper del zip
    this.$wrapMunicipality = this.$('#wrap_municipality');
    this.$wrapParish = this.$('#wrap_parish');

    // presets (opcionales)
    this.presetCountry = String(this.$('#preset_country_id').val() || '');
    this.presetState = String(this.$('#preset_state_id').val() || '');
    this.presetCity = String(this.$('#preset_city_id').val() || '');
    this.presetMunicipality = String(this.$('#preset_municipality_id').val() || '');
    this.presetParish = String(this.$('#preset_parish_id').val() || '');

    // estado inicial
    if (this.presetCountry && !this.$country.val()) this.$country.val(this.presetCountry);
    const countryId = this.$country.val();
    if (!countryId) {
      this._hide(this.$wrapState);
      this._hide(this.$wrapCity);
      this._hide(this.$wrapZip);
      this._hide(this.$wrapMunicipality);
      this._hide(this.$wrapParish);
      return res;
    }

    const hasStates = await this._loadStates(countryId, this.presetState).catch(() => false);
    this._toggle(this.$wrapState, hasStates);

    const stateId = this.$state.val();
    if (stateId) {
      // ciudades y municipios en paralelo
      const [hasCities, hasM] = await Promise.all([
        this._loadCities(stateId, this.presetCity).catch(() => false),
        this._loadMunicipalitiesByState(stateId, this.presetMunicipality).catch(() => false),
      ]);
      this._toggle(this.$wrapCity, hasCities);
      this._toggle(this.$wrapZip, hasCities); // zip junto con ciudad
      this._toggle(this.$wrapMunicipality, hasM);

      // si ya hay municipio (por preset), intenta cargar parroquias
      await this._maybeLoadParishes();
    } else {
      this._hide(this.$wrapCity);
      this._hide(this.$wrapZip);
      this._hide(this.$wrapMunicipality);
      this._hide(this.$wrapParish);
    }

    return res;
  },

  // --- Eventos ---
  async _onCountryChange(ev) {
    const countryId = ev.currentTarget.value;

    // reset inferiores
    this._fillOptions(this.$parish, [], 'Selecciona tu parroquia'); this._hide(this.$wrapParish);
    this._fillOptions(this.$municipality, [], 'Selecciona tu municipio'); this._hide(this.$wrapMunicipality);
    this._fillOptions(this.$city, [], 'Selecciona tu ciudad'); this._hide(this.$wrapCity);
    if (this.$zip && this.$zip.length) this.$zip.val(''); this._hide(this.$wrapZip);
    this._fillOptions(this.$state, [], 'Selecciona tu estado'); this._hide(this.$wrapState);

    if (!countryId) return;

    const hasStates = await this._loadStates(countryId, null).catch(() => false);
    this._toggle(this.$wrapState, hasStates);
    if (hasStates) this.$state.trigger('focus');
  },

  async _onStateChange(ev) {
    const stateId = ev.currentTarget.value;

    // reset inferiores
    this._fillOptions(this.$parish, [], 'Selecciona tu parroquia'); this._hide(this.$wrapParish);
    this._fillOptions(this.$municipality, [], 'Selecciona tu municipio'); this._hide(this.$wrapMunicipality);
    this._fillOptions(this.$city, [], 'Selecciona tu ciudad'); this._hide(this.$wrapCity);
    if (this.$zip && this.$zip.length) this.$zip.val(''); this._hide(this.$wrapZip);

    if (!stateId) return;

    // ciudades y municipios en paralelo
    const [hasCities, hasM] = await Promise.all([
      this._loadCities(stateId, null).catch(() => false),
      this._loadMunicipalitiesByState(stateId, null).catch(() => false),
    ]);
    this._toggle(this.$wrapCity, hasCities);
    this._toggle(this.$wrapZip, hasCities); // zip junto con ciudad
    this._toggle(this.$wrapMunicipality, hasM);

    // si ya hay municipio seleccionado (por autofill/preset), carga parroquias
    await this._maybeLoadParishes();
  },

  async _onCityChange(/*ev*/) {
    // municipios NO dependen de ciudad (en tu regla), así que solo manejamos parroquias y zip
    this._fillOptions(this.$parish, [], 'Selecciona tu parroquia'); this._hide(this.$wrapParish);
    // zip se mantiene visible por depender del estado/ciudad; solo limpiar si cambias ciudad
    if (this.$zip && this.$zip.length) this.$zip.val('');
    await this._maybeLoadParishes();
  },

  async _onMunicipalityChange(/*ev*/) {
    // cuando cambia municipio, intentamos cargar parroquias
    await this._maybeLoadParishes();
  },

  // zip: solo números
  _onZipInput(ev) {
    const clean = (ev.target.value || '').replace(/\D/g, '');
    if (ev.target.value !== clean) {
      ev.target.value = clean;
    }
  },

  // --- helper para parroquias ---
  async _maybeLoadParishes() {
    const municipalityId = this.$municipality.val();
    if (!municipalityId) {
      this._fillOptions(this.$parish, [], 'Selecciona tu parroquia');
      this._hide(this.$wrapParish);
      return false;
    }
    const hasP = await this._loadParishes(municipalityId, this.presetParish || null).catch(() => false);
    this._toggle(this.$wrapParish, hasP);
    if (hasP) this.$parish.trigger('focus');
    return hasP;
  },

  // --- helpers UI ---
  _show($el){ if ($el && $el.length) $el.removeClass('d-none'); },
  _hide($el){ if ($el && $el.length) $el.addClass('d-none'); },
  _toggle($el, cond){ cond ? this._show($el) : this._hide($el); },

  _fillOptions($select, items, placeholder) {
    if (!$select || !$select.length) return;
    const prev = $select.val() || '';
    $select.empty();
    $select.append($('<option>', { value: '', text: placeholder || 'Seleccione...' }));
    (items || []).forEach(it => {
      $select.append($('<option>', { value: String(it.id), text: it.name }));
    });
    const exists = (items || []).some(i => String(i.id) === String(prev));
    $select.val(exists ? prev : '');
  },

  // --- loaders (GET) ---
  async _loadStates(countryId, selectedId) {
    const resp = await fetch('/cadipa/location/states?country_id=' + countryId, { method: 'GET', credentials: 'same-origin' });
    if (!resp.ok) throw new Error('HTTP ' + resp.status);
    const data = await resp.json();
    this._fillOptions(this.$state, data, 'Selecciona tu estado');
    if (selectedId) this.$state.val(String(selectedId));
    return (data || []).length > 0;
  },

  async _loadCities(stateId, selectedId) {
    const resp = await fetch('/cadipa/location/cities?state_id=' + stateId, { method: 'GET', credentials: 'same-origin' });
    if (!resp.ok) throw new Error('HTTP ' + resp.status);
    const data = await resp.json();
    this._fillOptions(this.$city, data, 'Selecciona tu ciudad');
    if (selectedId) this.$city.val(String(selectedId));
    return (data || []).length > 0;
  },

  // Municipios por estado (no por ciudad)
  async _loadMunicipalitiesByState(stateId, selectedId) {
    const resp = await fetch('/cadipa/location/municipalities?state_id=' + stateId, { method: 'GET', credentials: 'same-origin' });
    if (!resp.ok) throw new Error('HTTP ' + resp.status);
    const data = await resp.json();
    this._fillOptions(this.$municipality, data, 'Selecciona tu municipio');
    if (selectedId) this.$municipality.val(String(selectedId));
    return (data || []).length > 0;
  },

  async _loadParishes(municipalityId, selectedId) {
    const resp = await fetch('/cadipa/location/parishes?municipality_id=' + municipalityId, { method: 'GET', credentials: 'same-origin' });
    if (!resp.ok) throw new Error('HTTP ' + resp.status);
    const data = await resp.json();
    this._fillOptions(this.$parish, data, 'Selecciona tu parroquia');
    if (selectedId) this.$parish.val(String(selectedId));
    return (data || []).length > 0;
  },
});
