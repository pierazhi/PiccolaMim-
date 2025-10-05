const express = require('express');
const path = require('path');
const fs = require('fs/promises');

const app = express();
const PORT = process.env.PORT || 3000;
const DATA_DIR = path.join(__dirname, 'data');
const DATA_FILE = path.join(DATA_DIR, 'captions.json');
const MAX_CAPTION_LENGTH = 2000;

app.use(express.json({ limit: '1mb' }));
app.use(express.static(__dirname));

app.get('/api/captions', async (req, res) => {
  try {
    const captions = await readCaptions();
    res.json(captions);
  } catch (err) {
    console.error('Unable to read captions:', err);
    res.status(500).json({ error: 'Impossibile leggere le descrizioni salvate.' });
  }
});

app.post('/api/captions', async (req, res) => {
  const { key, caption } = req.body || {};
  if (typeof key !== 'string' || !key.trim()) {
    return res.status(400).json({ error: 'Chiave mancante o non valida.' });
  }
  const safeKey = key.trim();
  const safeCaption = typeof caption === 'string' ? caption.trim().slice(0, MAX_CAPTION_LENGTH) : '';

  try {
    const captions = await readCaptions();
    captions[safeKey] = safeCaption;
    await writeCaptions(captions);
    res.json({ ok: true });
  } catch (err) {
    console.error('Unable to save caption:', err);
    res.status(500).json({ error: 'Impossibile salvare la descrizione.' });
  }
});

app.listen(PORT, () => {
  console.log(`Server in ascolto su http://localhost:${PORT}`);
});

async function readCaptions() {
  try {
    const raw = await fs.readFile(DATA_FILE, 'utf8');
    const parsed = JSON.parse(raw);
    if (parsed && typeof parsed === 'object') {
      return parsed;
    }
  } catch (err) {
    if (err.code === 'ENOENT') {
      return {};
    }
    throw err;
  }
  return {};
}

async function writeCaptions(data) {
  await fs.mkdir(DATA_DIR, { recursive: true });
  await fs.writeFile(DATA_FILE, JSON.stringify(data, null, 2), 'utf8');
}
