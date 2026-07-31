/** FPS counter and simulation-time display, both backed by #fps/#sim-time. */

export class FPS {
  constructor(div) {
    this.div = div;
    this.samples = new Array(10).fill(0);
    this.i = 0;
    this.lastFrame = performance.now();
  }

  frame() {
    const now = performance.now();
    const delta = now - this.lastFrame;
    this.lastFrame = now;

    this.samples[this.i] = 1000 / delta;
    this.i = (this.i + 1) % this.samples.length;

    const avg = this.samples.reduce((a, b) => a + b, 0) / this.samples.length;
    this.div.innerHTML = `${Math.round(avg)} fps`;
  }
}

export class SimTime {
  constructor(div) {
    this.div = div;
  }

  display(t) {
    const totalSeconds = Math.floor(t);
    const m = String(Math.floor(totalSeconds / 60)).padStart(2, "0");
    const s = String(totalSeconds % 60).padStart(2, "0");
    const ms = String(Math.round((t * 1000) % 1000)).padStart(3, "0");
    this.div.innerHTML = `${m}:${s}.${ms}`;
  }
}
