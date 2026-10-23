/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // برای ایمیج کوچک Docker (server.js مستقل)
  output: "standalone",

  // ⚠️ پروکسی بک‌اند اینجا نیست: `rewrites()` فقط در زمان build ارزیابی
  // می‌شود و آدرس بک‌اند را در routes-manifest قفل می‌کند؛ نتیجه این بود که
  // روی PaaS (که بک‌اند یک برنامهٔ جدا با آدرس دیگر است) همه‌چیز می‌شکست.
  // پروکسی در `app/api/[...path]/route.ts` است و BACKEND_INTERNAL_URL را
  // در زمان اجرا می‌خواند.

  async headers() {
    return [
      {
        /**
         * فونت‌ها از قاب سندباکس‌شده (origin = null) درخواست می‌شوند و بدون
         * هدر CORS مرورگر آن‌ها را بلاک می‌کند → صفحه با فونت جایگزین رندر
         * می‌شد. این هدر فقط برای فایل‌های استاتیک فونت است و داده‌ای افشا نمی‌کند.
         */
        source: "/fonts/:path*",
        headers: [
          { key: "Access-Control-Allow-Origin", value: "*" },
          { key: "Cache-Control", value: "public, max-age=31536000, immutable" },
        ],
      },
      {
        // تصاویر محلی (آواتارها/جای‌گزین‌ها) هم ممکن است داخل قاب لود شوند
        source: "/:path*.(png|jpg|jpeg|svg|webp|woff2)",
        headers: [{ key: "Access-Control-Allow-Origin", value: "*" }],
      },
    ];
  },
};

module.exports = nextConfig;
