require('dotenv').config();
const { client } = require('./src/openSearch');

(async () => {
  try {
    await client.indices.putSettings({
      index: 'dataset_progress_sessions',
      body: {
        refresh_interval: '5s',
      },
    });
    require('./src/server');
  } catch (error) {
    console.error('Error:', error);
  }
})();
