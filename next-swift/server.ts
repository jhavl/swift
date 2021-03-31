const express = require('express')
const next = require('next')
const dev = process.env.NODE_ENV !== 'production'
const app = next({'dev': dev})
const handle = app.getRequestHandler()

app.prepare().then(() => {
  const server = express()
    
  server.get(['*.dae', '*.stl'], (req, res) => {
    res.sendFile(req.path)
  })

//   server.get('/[0-9]{5}/', (req, res) => {
//     console.log(req.path)
//     res.path = '/'
//     console.log(req.path)
//     return handle(req, res)
//   })

  server.get('*', (req, res) => {
    return handle(req, res)
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
// 