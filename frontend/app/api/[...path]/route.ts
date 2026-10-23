import { NextRequest } from "next/server";

/**
 * پروکسی `/api/*` → بک‌اند، با آدرس **زمان اجرا**.
 *
 * چرا route handler و نه `rewrites` در next.config؟
 * `rewrites()` فقط یک‌بار در زمان build اجرا می‌شود و مقصد در
 * `.next/routes-manifest.json` قفل می‌شود. یعنی متغیر
 * `BACKEND_INTERNAL_URL` در زمان اجرا هیچ اثری نداشت و مقدار زمان build
 * (پیش‌فرض `http://127.0.0.1:8000`) استفاده می‌شد. روی یک PaaS که بک‌اند و
 * فرانت دو برنامهٔ جدا هستند (مثلاً لیارا: `http://torob-api:8000`)، این
 * باعث می‌شد همهٔ درخواست‌ها شکست بخورند.
 *
 * این فایل همان مسیر را در زمان اجرا می‌خواند: یک ایمیج، چند محیط.
 */

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const BACKEND = (
  process.env.BACKEND_INTERNAL_URL ||
  process.env.API_INTERNAL_URL ||
  "http://127.0.0.1:8000"
).replace(/\/+$/, "");

/** هدرهای درخواست که باید به بک‌اند برسند */
const FORWARD_REQUEST_HEADERS = [
  "content-type",
  "accept",
  "accept-language",
  "authorization",
  "user-agent",
];

/** هدرهای پاسخ که به مرورگر برمی‌گردند */
const FORWARD_RESPONSE_HEADERS = [
  "content-type",
  "content-disposition",
  "cache-control",
  "etag",
];

async function proxy(req: NextRequest, ctx: { params: { path: string[] } }) {
  const { path } = ctx.params;
  const search = new URL(req.url).search;
  const target = `${BACKEND}/api/${(path ?? []).join("/")}${search}`;

  const headers = new Headers();
  for (const name of FORWARD_REQUEST_HEADERS) {
    const value = req.headers.get(name);
    if (value) headers.set(name, value);
  }

  const hasBody = !["GET", "HEAD"].includes(req.method);

  try {
    const upstream = await fetch(target, {
      method: req.method,
      headers,
      body: hasBody ? await req.arrayBuffer() : undefined,
      redirect: "manual",
      cache: "no-store",
      // بدون این، Next نتیجه را کش می‌کند و پاسخ‌های ایجنت کهنه می‌شوند
      signal: AbortSignal.timeout(60_000),
    });

    const outHeaders = new Headers();
    for (const name of FORWARD_RESPONSE_HEADERS) {
      const value = upstream.headers.get(name);
      if (value) outHeaders.set(name, value);
    }
    if (!outHeaders.has("content-type")) {
      outHeaders.set("content-type", "application/json; charset=utf-8");
    }

    return new Response(upstream.body, {
      status: upstream.status,
      headers: outHeaders,
    });
  } catch (err) {
    const reason = err instanceof Error ? err.message : "unknown";
    console.error(`[api-proxy] ${req.method} ${target} → ${reason}`);
    return Response.json(
      {
        detail:
          "ارتباط با سرویس بک‌اند برقرار نشد. اگر روی لیارا هستید، " +
          "BACKEND_INTERNAL_URL را روی آدرس شبکهٔ خصوصی برنامهٔ API تنظیم کنید.",
        target,
      },
      { status: 502 },
    );
  }
}

export const GET = proxy;
export const POST = proxy;
export const PUT = proxy;
export const PATCH = proxy;
export const DELETE = proxy;
export const HEAD = proxy;
export const OPTIONS = proxy;
