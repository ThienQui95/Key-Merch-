import { NextResponse } from "next/server";
import { createClient } from "@supabase/supabase-js";

const supabase = createClient(
  process.env.SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_ROLE_KEY!,
  { auth: { persistSession: false } }
);

export async function GET() {
  return NextResponse.json({ ok: true, hint: "POST JSON { key } to this URL" });
}

export async function POST(req: Request) {
  try {
    const body = await req.json().catch(() => ({} as any));
    const key = (body?.key ?? "").trim();
    if (!key) return NextResponse.json({ error: "missing key" }, { status: 400 });

    const { data, error } = await supabase
      .from("licenses")
      .select("license_key, is_active, expires_at, plan, owner_email")
      .eq("license_key", key)
      .limit(1)
      .maybeSingle();

    if (error) return NextResponse.json({ status: "error", message: "db_error" }, { status: 500 });

    const now = new Date();
    const valid = !!data && data.is_active === true &&
                  (!data.expires_at || new Date(data.expires_at) > now);

    if (!valid) {
      return NextResponse.json(
        { status: "success", valid: false, reason: !data ? "not_found" : data.is_active === false ? "inactive" : "expired" },
        { status: 200 }
      );
    }

    return NextResponse.json(
      { status: "success", valid: true, plan: data.plan ?? "pro", owner: data.owner_email ?? null, expiry: data.expires_at ?? null },
      { status: 200 }
    );
  } catch {
    return NextResponse.json({ status: "error", message: "internal" }, { status: 500 });
  }
}
