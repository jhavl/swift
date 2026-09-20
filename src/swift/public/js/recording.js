/**
 * Screen recording. "webm" uses the browser's native MediaRecorder
 * (broadly supported, no extra dependency) -- the other formats ("gif",
 * "png", "jpg") still go through CCapture (loaded globally from
 * js/vendor/build/ccapture.umd.min.js -- not imported as an ES module
 * here, so it stays a classic global script).
 *
 * CCapture 1.x's own webm encoder muxed per-frame WebP images
 * (canvas.toDataURL("image/webp")), which Safari has never supported
 * from a canvas -- it failed there with "WebP not supported" /
 * "Couldn't decode WebP frame" and produced an empty (frameless) file
 * every time, silently (found 2026-07-26 producing a 243-byte "video").
 * MediaRecorder doesn't go through WebP at all, so it doesn't have this
 * gap -- webm moved to it for that reason. gif/png/jpg never used
 * CCapture's WebP path, so they're unaffected and still use CCapture
 * (now 2.x: png/jpg now download as a .tar of frames rather than
 * whatever 1.x packaged them as, and gif moved to the gifenc encoder --
 * see the ccapture.js 2.x migration guide).
 */

export class Recorder {
  /** @param {HTMLCanvasElement} canvas */
  constructor(canvas) {
    this.canvas = canvas;
    this.active = false;
    /** gif format needs the tab to stay open for the user to save it. */
    this.autoclose = true;

    this._legacyCapturer = null; // CCapture instance, for gif/png/jpg
    this._mediaRecorder = null;
    this._chunks = [];
    this._fileName = null;
  }

  start(framerate, name, format) {
    if (this.active) return;
    this._fileName = name;

    if (format === "webm") {
      this._mediaRecorder = new MediaRecorder(this.canvas.captureStream(framerate), {
        mimeType: "video/webm",
      });
      this._chunks = [];
      this._mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) this._chunks.push(e.data);
      };
      this._mediaRecorder.start();
    } else {
      if (format === "gif") this.autoclose = false;
      this._legacyCapturer = new CCapture({
        verbose: false,
        display: true,
        framerate,
        quality: 100,
        format,
        name,
      });
      this._legacyCapturer.start();
    }

    this.active = true;
  }

  /** No-op for the MediaRecorder path -- captureStream() samples the
   * canvas on its own schedule. Only CCapture's formats need an explicit
   * per-frame grab. */
  captureFrame(canvas) {
    if (this.active && this._legacyCapturer) this._legacyCapturer.capture(canvas);
  }

  stop() {
    if (this._legacyCapturer) {
      this._legacyCapturer.stop();
      this._legacyCapturer.save();
      this._legacyCapturer = null;
    } else if (this._mediaRecorder) {
      this._mediaRecorder.onstop = () => {
        const url = URL.createObjectURL(new Blob(this._chunks, { type: "video/webm" }));
        const link = document.createElement("a");
        link.href = url;
        link.download = `${this._fileName}.webm`;
        link.click();
        URL.revokeObjectURL(url);
      };
      this._mediaRecorder.stop();
      this._mediaRecorder = null;
    }

    this.active = false;
  }
}
