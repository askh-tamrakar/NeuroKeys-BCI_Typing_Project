import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import fs from 'fs'
import path from 'path'

console.log('--- VITE CONFIG LOADING ---');

// Custom Plugin for File Saving
const saveDetailsPlugin = () => ({
  name: 'save-details-middleware',
  configureServer(server) {
    console.log('--- MIDDLEWARE REGISTERED ---');
    server.middlewares.use((req, res, next) => {
      // Exact match for the internal route
      if (req.url === '/_internal/save-details' && req.method === 'POST') {
        console.log('Middleware intercepted request!');
        let body = '';
        req.on('data', chunk => { body += chunk.toString() });
        req.on('end', () => {
          try {
            // Locate detail.json
            const locations = [
              path.resolve(process.cwd(), 'detail.json'),
              path.resolve(process.cwd(), 'frontend', 'detail.json') // In case cwd is root
            ];

            // Prefer existing or default to first
            let filePath = locations.find(p => fs.existsSync(p)) || locations[0];

            console.log('Writing to:', filePath);

            let existingData = [];
            if (fs.existsSync(filePath)) {
              try {
                existingData = JSON.parse(fs.readFileSync(filePath, 'utf-8'));
                if (!Array.isArray(existingData)) existingData = [];
              } catch (e) { existingData = []; }
            }

            const newData = JSON.parse(body);
            existingData.push(newData);

            fs.writeFileSync(filePath, JSON.stringify(existingData, null, 2));

            res.setHeader('Content-Type', 'application/json');
            res.end(JSON.stringify({ status: 'success' }));
          } catch (err) {
            console.error('Middleware Write Error:', err);
            res.statusCode = 500;
            res.end(JSON.stringify({ error: err.toString() }));
          }
        });
      } else {
        next();
      }
    });
  }
});

export default defineConfig({
  plugins: [
    react(),
    saveDetailsPlugin() // Add our custom plugin here
  ],
  server: {
    port: 7219,
    open: true,
    proxy: {
      '/api': {
        target: 'http://localhost:5000',
        changeOrigin: true,
        secure: false,
      },
      '/socket.io': {
        target: 'http://localhost:5000',
        changeOrigin: true,
        ws: true,
      }
    },
    allowedHosts: ["squelchingly-thriftier-cecile.ngrok-free.dev"]
  }
})
