###Install
```
# Install node js version 12.18.2 (or whatever LTS is on a mac)
https://nodejs.org/en/

# Clone the repo
git clone git@github.com:jhavl/sim.git 
# or 
git clone https@github.com:jhavl/sim.git 

# cd into directory
cd sim

# Install the project (this will download and install the dependancies for the project)
npm install

# Start the program
npm start 
```

### Information
Node is a server framework (or so I think) for acting as the backend for
websites, apps, webapps and appwebs (probably).

So in a typical application the node server has access to all of the powerful
and usefull modules you can find on npm (pip for node), while the client
(web browser) is much more limited in capability. In this project the main
server code is in src/index.js

Electron joins the server and client together since it runs in a desktop
environment and brings to power of the server to the client. So all Node
modules on npm can run on the client with electron. In this project the main
client js code is src/renderer.js
