const http = require("http");

const port = process.env.PORT || 3000;

http
  .createServer((req, res) => {
    res.writeHead(200, { "Content-Type": "text/plain" });
    res.end("Hello from DevEnv Hub (node template)\n");
  })
  .listen(port, () => console.log(`listening on ${port}`));
