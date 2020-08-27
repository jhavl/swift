const { app, BrowserWindow, protocol } = require('electron');
const path = require('path');
let {extname} = require('path');
const tr = require('three')
require('electron-reload')(__dirname);
let {readFile} = require("fs");
let {URL} = require("url");

// Base path used to resolve modules
const base = app.getAppPath();

// Protocol will be "app://./…"
const scheme = 'app';

// { /* Protocol */
//   // Registering must be done before app::ready fires
//   // (Optional) Technically not a standard scheme but works as needed
//   protocol.registerSchemesAsPrivileged([{
//     scheme: 'app',
//     privileges: {
//       standard: true,
//       secure: true,
//       supportFetchAPI: true
//     }}]);

//   // Create protocol
//   require('./lib/create-protocol')(scheme, base);
// }

let createProtocol = (scheme, normalize = true) => {
  protocol.registerBufferProtocol(scheme,
    (request, respond) => {
      let pathName = new URL(request.url).pathname;
      pathName = decodeURI(pathName); // Needed in case URL contains spaces
    
      readFile(__dirname + "/" + pathName, (error, data) => {
        let extension = extname(pathName).toLowerCase();
        let mimeType = "";

        if (extension === ".js") {
          mimeType = "text/javascript";
        }
        else if (extension === ".mjs") {
          mimeType = "text/javascript";
        }
        else if (extension === ".html") {
          mimeType = "text/html";
        }
        else if (extension === ".css") {
          mimeType = "text/css";
        }
        else if (extension === ".svg" || extension === ".svgz") {
          mimeType = "image/svg+xml";
        }
        else if (extension === ".json") {
          mimeType = "application/json";
        }

        respond({mimeType, data}); 
      });
    },
    (error) => {
      if (error) {
        console.error(`Failed to register ${scheme} protocol`, error);
      }
    }
  );
}

// Standard scheme must be registered before the app is ready
// protocol.registerStandardSchemes(["app"], { secure: true });


// Handle creating/removing shortcuts on Windows when installing/uninstalling.
if (require('electron-squirrel-startup')) { // eslint-disable-line global-require
  app.quit();
}

const createWindow = () => {
  // Create the browser window.
  const mainWindow = new BrowserWindow({
    frame: false,
    autoHideMenuBar: true,
    webPreferences: {
      nodeIntegration: true
    } ,
    width: 800,
    height: 600
  });

  // and load the index.html of the app.
  mainWindow.loadFile(path.join(__dirname, 'index.html'));
};

// This method will be called when Electron has finished
// initialization and is ready to create browser windows.
// Some APIs can only be used after this event occurs.
app.on('ready', () => {
  createProtocol("app");
  createWindow();
});

// Quit when all windows are closed, except on macOS. There, it's common
// for applications and their menu bar to stay active until the user quits
// explicitly with Cmd + Q.
app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('activate', () => {
  // On OS X it's common to re-create a window in the app when the
  // dock icon is clicked and there are no other windows open.
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});

// In this file you can include the rest of your app's specific main process
// code. You can also put them in separate files and import them here.

