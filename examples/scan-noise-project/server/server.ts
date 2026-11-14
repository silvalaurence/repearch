// Sprint-one prototype. Nothing in src/ imports this file and the client never calls
// it, but it is still sitting in the repo - exactly what the wiring check must catch.
import express from "express";
import { router } from "./routes";

const app = express();
const PORT = 3000;

app.use("/api", router);
console.log("terminal colour:", process.env.COLORTERM);

app.listen(PORT, () => console.log(`listening on ${PORT}`));
