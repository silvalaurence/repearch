import { Router } from "express";

const router = Router();
const courts: Record<string, unknown>[] = [];

router.get("/api/courts", (_req, res) => res.json(courts));
router.post("/api/sessions", (req, res) => {
  courts.push(req.body);
  res.status(201).json({ ok: true });
});

export { router };
