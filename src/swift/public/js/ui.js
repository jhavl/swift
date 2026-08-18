/**
 * User-defined UI controls (Slider/Button/Label/Select/Checkbox/Radio),
 * injected into #sidenav -- except the built-in pause/realtime-speed
 * controls Swift.py adds itself (Button/Select constructed with
 * `data.builtin: true`, see Swift._add_controls()), which go into the
 * separate #control-panel instead. Each instance exposes `.changed`/
 * `.data`; main.js collects changed elements into the response it sends
 * back with every "shape_poses" message (Swift.py's per-step pose push
 * doubles as the UI-element-change channel -- there's no separate polling
 * message).
 */

const shown = { sidenav: false, "control-panel": false };

function insert(html, containerId = "sidenav") {
  if (!shown[containerId]) {
    document.getElementById(containerId).style.display = containerId === "control-panel" ? "flex" : "block";
    shown[containerId] = true;
  }
  document.getElementById(containerId).insertAdjacentHTML("beforeend", html);
}

export class Slider {
  constructor(data) {
    insert(`
      <div class="slider-div" id="slider-div${data.id}">
        <p class="slider-p" id="desc${data.id}"></p>
        <input type="range" value="0" step="1" min="0" max="100" class="slider" id="slider${data.id}">
        <div class="slider-val-div" id="slider-val-div${data.id}">
          <p class="slider-vals slider-min" id="min${data.id}">0</p>
          <p class="slider-vals slider-val" id="value${data.id}">0</p>
          <p class="slider-vals slider-max" id="max${data.id}">100</p>
        </div>
      </div>
    `);

    this.id = data.id;
    this.slider = document.getElementById(`slider${data.id}`);
    this.value = document.getElementById(`value${data.id}`);
    this.min = document.getElementById(`min${data.id}`);
    this.max = document.getElementById(`max${data.id}`);
    this.desc = document.getElementById(`desc${data.id}`);

    this.onInput = () => {
      // toFixed(), not toPrecision() -- this.precision is decimal places
      // (2.478 at precision=3), not significant figures (2.48 at 3 sig
      // figs -- a different, narrower value this does not implement).
      // Rounds for display only -- the slider's own value (used for
      // this.data/the actual reported value) keeps its raw float
      // precision, e.g. any float step()-side arithmetic that produced
      // it (0.30000000000000004 and the like).
      this.value.innerHTML = Number(this.slider.value).toFixed(this.precision) + this.unit;
      this.changed = true;
      this.data = Number(this.slider.value);
    };
    this.slider.addEventListener("input", this.onInput);

    this.changed = false;
    this.update(data);
  }

  update(data) {
    this.unit = data.unit;
    this.precision = data.precision;
    this.slider.value = data.value;
    this.slider.step = data.step;
    this.slider.min = data.min;
    this.slider.max = data.max;
    // The slider's own min/max (above) keep full precision -- only the
    // text labels are rounded, same as the live value. Otherwise a range
    // like min=-np.pi/max=np.pi shows -3.141592653589793 regardless of
    // precision=, since these were never touched by that fix at all.
    this.min.innerHTML = Number(data.min).toFixed(data.precision);
    this.max.innerHTML = Number(data.max).toFixed(data.precision);
    this.desc.innerHTML = data.desc;
    this.onInput();
  }
}

export class Button {
  constructor(data) {
    const btnClass = data.builtin ? "control-button" : "button-button";
    insert(
      `
      <div class="${data.builtin ? "control-button-div" : "button-div"}">
        <button type="button" class="${btnClass}" id="button${data.id}"></button>
      </div>
    `,
      data.builtin ? "control-panel" : "sidenav"
    );

    this.id = data.id;
    this.button = document.getElementById(`button${data.id}`);
    this.onInput = () => {
      this.changed = true;
    };
    this.button.addEventListener("click", this.onInput);

    this.changed = false;
    this.data = 0;
    this.update(data);
  }

  update(data) {
    this.button.innerHTML = data.desc;
  }
}

export class Label {
  constructor(data) {
    insert(`<div class="label-div"><p id="label${data.id}"></p></div>`);

    this.id = data.id;
    this.label = document.getElementById(`label${data.id}`);
    this.changed = false;
    this.data = 0;
    this.update(data);
  }

  update(data) {
    this.label.innerHTML = data.desc;
  }
}

export class Select {
  constructor(data) {
    const selectClass = data.builtin ? "control-select" : "select-select";
    // Builtin controls (the speed selector) skip the label -- the panel
    // is small and self-explanatory, a "Speed" caption would be clutter.
    insert(
      data.builtin
        ? `<select id="select${data.id}" class="${selectClass}"></select>`
        : `
      <div class="select-div">
        <label id="label${data.id}" class="select-label"></label>
        <select id="select${data.id}" class="${selectClass}"></select>
      </div>
    `,
      data.builtin ? "control-panel" : "sidenav"
    );

    this.id = data.id;
    this.label = document.getElementById(`label${data.id}`);
    this.select = document.getElementById(`select${data.id}`);
    this.onInput = () => {
      this.changed = true;
      this.data = this.select.value;
    };
    this.select.addEventListener("change", this.onInput);

    this.changed = false;
    this.data = 0;
    this.update(data);
  }

  update(data) {
    if (this.label) this.label.innerHTML = data.desc;
    this.select.innerHTML = data.options
      .map((opt, i) => `<option value="${i}">${opt}</option>`)
      .join("");
    this.select.value = String(data.value);
  }
}

export class Checkbox {
  constructor(data) {
    insert(`
      <div class="checkbox-div">
        <p id="label${data.id}"></p>
        <div class="checkbox-cont" id="checkboxcont${data.id}"></div>
      </div>
    `);

    this.id = data.id;
    this.label = document.getElementById(`label${data.id}`);
    this.checkbox = document.getElementById(`checkboxcont${data.id}`);
    this.onChange = () => {
      this.changed = true;
      this.data = [...this.checkbox.getElementsByTagName("input")].map((c) => c.checked);
    };
    this.checkbox.addEventListener("change", this.onChange);

    this.changed = false;
    this.data = [];
    this.update(data);
  }

  update(data) {
    this.label.innerHTML = data.desc;
    this.checkbox.innerHTML = data.options
      .map((opt, i) => {
        const checked = data.checked[i] ? "checked" : "";
        return `<label for="checkbox${this.id}"><input type="checkbox" ${checked} id="checkbox${this.id}${i}" /><span>${opt}</span></label>${
          i < data.options.length - 1 ? "<br>" : ""
        }`;
      })
      .join("");
    this.onChange();
  }
}

export class Radio {
  constructor(data) {
    insert(`
      <div class="radio-div">
        <p id="label${data.id}"></p>
        <div class="radio-cont" id="radiocont${data.id}"></div>
      </div>
    `);

    this.id = data.id;
    this.label = document.getElementById(`label${data.id}`);
    this.radio = document.getElementById(`radiocont${data.id}`);
    this.onChange = () => {
      this.changed = true;
      const radios = [...this.radio.getElementsByTagName("input")];
      const checked = radios.findIndex((r) => r.checked);
      if (checked !== -1) this.data = checked;
    };
    this.radio.addEventListener("change", this.onChange);

    this.changed = false;
    this.data = [];
    this.update(data);
  }

  update(data) {
    this.label.innerHTML = data.desc;
    this.radio.innerHTML = data.options
      .map((opt, i) => {
        const checked = data.checked === i ? "checked" : "";
        return `<label for="radio${this.id}"><input type="radio" ${checked} id="radio${this.id}${i}" name="radio${this.id}"/><span>${opt}</span></label>${
          i < data.options.length - 1 ? "<br>" : ""
        }`;
      })
      .join("");
    this.onChange();
  }
}
