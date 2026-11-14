CREATE TABLE public.court_hours (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    court_id bigint REFERENCES public.courts NOT NULL,
    opens time NOT NULL,
    closes time NOT NULL
);

CREATE OR REPLACE FUNCTION public.add_booking(p_member bigint, p_court bigint, p_starts timestamp)
RETURNS bigint
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO public.bookings (member_id, court_id, starts_at)
    VALUES (p_member, p_court, p_starts)
    RETURNING id;
END;
$$;
