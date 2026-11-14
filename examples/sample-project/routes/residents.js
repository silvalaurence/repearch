const express = require('express');
const router = express.Router();
router.get('/residents', (req, res) => { const key = process.env.JWT_SECRET; res.json([]); });
router.post('/residents', (req, res) => { res.status(201).end(); });
module.exports = router;
