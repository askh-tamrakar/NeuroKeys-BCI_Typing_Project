const fs = require('fs');
const path = require('path');

// Create directory structure
const dirs = [
  'src/components/auth',
  'src/components/dashboard',
  'src/components/charts',
  'src/components/views',
  'src/contexts',
  'src/hooks',
  'src/services',
  'src/styles'
];

dirs.forEach(dir => {
  const fullPath = path.join(__dirname, dir);
  if (!fs.existsSync(fullPath)) {
    fs.mkdirSync(fullPath, { recursive: true });
    console.log(`✓ Created ${dir}`);
  }
});

console.log('\n✅ All directories created!');
console.log('\nNow create the component files from the previous messages.');
