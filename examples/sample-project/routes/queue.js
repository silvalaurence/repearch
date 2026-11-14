const express = require('express');
const router = express.Router();
// TODO: add pagination
router.get('/queue', (req, res) => { const host = process.env.DB_HOST; res.json([]); });
router.post('/queue', (req, res) => { res.status(201).end(); });
router.put('/queue/:id/call', (req, res) => { res.end(); });
module.exports = router;
