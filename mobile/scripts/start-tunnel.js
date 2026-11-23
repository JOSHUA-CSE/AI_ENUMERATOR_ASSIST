const localtunnel = require('localtunnel');
const fs = require('fs');
const path = require('path');

(async () => {
  const port = 8000;
  console.log(`Starting localtunnel for FastAPI on port ${port}...`);

  try {
    const tunnel = await localtunnel({ port });

    console.log(`\n==============================================`);
    console.log(` TUNNEL READY FOR FASTAPI`);
    console.log(` Public URL: ${tunnel.url}`);
    console.log(` API Endpoint: ${tunnel.url}/api/v1`);
    console.log(`==============================================\n`);

    // Write to .env
    const envPath = path.join(__dirname, '..', '.env');
    const envContent = `EXPO_PUBLIC_API_URL=${tunnel.url}/api/v1\n`;
    fs.writeFileSync(envPath, envContent, 'utf-8');
    console.log(`Updated mobile/.env with EXPO_PUBLIC_API_URL=${tunnel.url}/api/v1`);

    tunnel.on('close', () => {
      console.log('Tunnel closed.');
    });

    tunnel.on('error', (err) => {
      console.error('Tunnel error:', err);
    });
  } catch (err) {
    console.error('Failed to start localtunnel:', err);
  }
})();
