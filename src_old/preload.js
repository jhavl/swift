let {protocol} = require("electron");

process.once("loaded", () => {
  // Allow window.fetch() to access app files
  protocol.registerURLSchemeAsPrivileged("app", {
    secure: true,
    bypassCSP: false,
    allowServiceWorkers: true,
    supportFetchAPI: true,
    corsEnabled: false
  });
});