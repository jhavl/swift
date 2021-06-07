const express = require('express')
const next = require('next')
const dev = process.env.NODE_ENV !== 'production'
const app = next({'dev': dev})
const handle = app.getRequestHandler()

app.prepare().then(() => {
  const server = express()

  server.get('*', (req, res) => {
    
    if (req.path.startsWith('/retrieve/')) {
      const path = req.path.slice(10);
      res.sendFile(path);
    } else {
      return handle(req, res)
    }
  })
    
  server.listen(3000, (err) => {
    if (err) throw err
    console.log('> Ready on http://localhost:3000')
  })
}).catch((ex) => {
  console.error(ex.stack)
  process.exit(1)
})

// export { }
