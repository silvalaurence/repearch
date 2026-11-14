CREATE TABLE public.members (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    full_name character varying(150) NOT NULL,
    email character varying(150) UNIQUE NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL
);

CREATE TABLE public.courts (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name character varying(80) NOT NULL,
    hourly_rate numeric(8,2) NOT NULL
);

CREATE TABLE public.bookings (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    member_id bigint REFERENCES public.members NOT NULL,
    court_id bigint REFERENCES public.courts NOT NULL,
    starts_at timestamp without time zone NOT NULL,
    status character varying(20) DEFAULT 'pending' NOT NULL,
    CONSTRAINT no_overlap UNIQUE (court_id, starts_at)
);
