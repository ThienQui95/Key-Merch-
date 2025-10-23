import { createClient } from '@supabase/supabase-js';

const supabase = createClient(
  process.env.SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_ROLE_KEY!
);

export async function GET() {
  return Response.json({ ok: true, hint: "POST JSON { key } to this URL" });
}

export async function POST(req: Request) {
  try {
    const { key } = await req.json();
    if (!key) return Response.json({ error: "Missing key" }, { status: 400 });

    const { data } = await supabase.from("licenses").select("*").eq("key", key).single();

    if (!data) return Response.json({ valid: false, message: "Key not found" });
    if (data.status !== "active") return Response.json({ valid: false, message: "Key inactive" });

    return Response.json({ valid: true, expires: data.expire_date });
  } catch (err) {
    console.error(err);
    return Response.json({ error: "Internal server error" }, { status: 500 });
  }
}
