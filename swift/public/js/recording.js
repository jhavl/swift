/**
 * Screen recording via CCapture (loaded globally from
 * js/vendor/build/CCapture.all.min.js -- it's not published as an ES
 * module, so it stays a classic global script rather than an import).
 */

export class Recorder {
  constructor() {
    this.active = false;
    this.capturer = null;
    /** gif format needs the tab to stay open for the user to save it. */
    this.autoclose = true;
  }

  start(framerate, name, format) {
    if (this.active) return;
    if (format === "gif") this.autoclose = false;

    this.capturer = new CCapture({
      verbose: false,
      display: true,
      framerate,
      quality: 100,
      format,
      name,
      workersPath: "js/vendor/build/",
    });
    this.active = true;
    this.capturer.start();
  }

  captureFrame(canvas) {
    if (this.active) this.capturer.capture(canvas);
  }

  stop() {
    this.capturer.stop();
    this.capturer.save();
    this.active = false;
  }
}
