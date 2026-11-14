import { createClient } from "@supabase/supabase-js";

const client = createClient("https://placeholder.supabase.co", "public-anon-key");

export async function loadBookings(courtId: string) {
  const { data, error } = await client.from("bookings").select("*").eq("court_id", courtId);
  if (error) throw error;
  return data;
}

export async function addBooking(userId: string, courtId: string, startsAt: string) {
  const { data, error } = await client.rpc("add_booking", {
    p_user: userId,
    p_court: courtId,
    p_starts: startsAt,
  });
  if (error) throw error;
  return data;
}
