const express = require('express');
const { Pool } = require('pg');

const app = express();
const pool = new Pool();
app.use(express.json({ limit: '8kb' }));

app.get('/health', async (_req, res) => {
  try {
    await pool.query('SELECT 1');
    res.json({ status: 'ok', service: 'node', database: 'connected' });
  } catch (_error) {
    res.status(503).json({ status: 'error', service: 'node', database: 'unavailable' });
  }
});

app.get('/messages', async (_req, res) => {
  try {
    const { rows } = await pool.query(
      'SELECT id, name, message, created_at FROM messages ORDER BY created_at DESC LIMIT 100'
    );
    res.json(rows);
  } catch (_error) {
    res.status(503).json({ error: '資料庫暫時無法使用' });
  }
});

app.post('/messages', async (req, res) => {
  const name = typeof req.body.name === 'string' ? req.body.name.trim().slice(0, 40) : '';
  const message = typeof req.body.message === 'string' ? req.body.message.trim().slice(0, 500) : '';
  if (!name || !message) return res.status(400).json({ error: '請填寫姓名與留言' });
  try {
    const { rows } = await pool.query(
      'INSERT INTO messages (name, message) VALUES ($1, $2) RETURNING id, name, message, created_at',
      [name, message]
    );
    res.status(201).json(rows[0]);
  } catch (_error) {
    res.status(503).json({ error: '資料庫暫時無法使用' });
  }
});

const port = Number(process.env.PORT || 3000);
app.listen(port, '0.0.0.0', () => console.log(`Node API listening on ${port}`));
