import { addBooking } from "../hooks/useSessions";

test("addBooking posts a row", async () => {
  expect(await addBooking("u1", "c1", "2026-01-01T10:00:00Z")).toBeDefined();
});
