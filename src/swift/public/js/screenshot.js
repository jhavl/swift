/** Screenshot saving: canvas -> PNG download, plus the auto-generated
 * filename used by the 's' hotkey (env.screenshot()'s own file_name
 * argument covers the explicit-name case). */

// Colons aren't valid in Windows filenames, so the timestamp uses dashes
// throughout rather than the `HH:MM:SS` grouping a clock display would use.
export function timestampedScreenshotName() {
  const pad = (n) => String(n).padStart(2, "0");
  const now = new Date();
  const date = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
  const time = `${pad(now.getHours())}-${pad(now.getMinutes())}-${pad(now.getSeconds())}`;
  return `swift-${date}_${time}`;
}

export function saveScreenshot(canvas, fileName) {
  const link = document.createElement("a");
  link.download = `${fileName}.png`;
  link.href = canvas.toDataURL("image/png");
  link.click();
}
