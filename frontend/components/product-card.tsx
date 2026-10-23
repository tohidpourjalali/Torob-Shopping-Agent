"use client";

import Link from "next/link";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

import { ProductImage } from "@/components/product-image";
import { formatCompactToman, formatNumber, type ProductSummary } from "@/lib/api";
import { ArrowLeft, Store, AlertCircle } from "lucide-react";

export function ProductCard({
  product,
  onSelect,
  selected,
  rank,
}: {
  product: ProductSummary;
  onSelect?: (p: ProductSummary) => void;
  selected?: boolean;
  rank?: number;
}) {
  const hasPrice = product.min_price_toman != null;

  return (
    <Card
      className={
        "overflow-hidden transition-shadow hover:shadow-md " +
        (selected ? "ring-2 ring-primary" : "")
      }
    >
      <CardContent className="p-3 sm:p-4">
        <div className="flex gap-3">
          {/* تصویر */}
          <div className="relative shrink-0">
            <ProductImage
              src={product.image_url}
              alt={product.persian_title || "محصول"}
              seed={product.product_id}
              className="h-20 w-20 sm:h-24 sm:w-24"
            />
            {rank != null && (
              <span className="absolute right-1 top-1 rounded-md bg-primary px-1.5 text-[11px] font-bold text-primary-foreground">
                {formatNumber(rank)}
              </span>
            )}
          </div>

          {/* متن */}
          <div className="min-w-0 flex-1">
            <Link
              href={`/product/${product.product_id}`}
              className="line-clamp-2 text-sm font-semibold leading-6 hover:text-primary sm:text-[15px]"
            >
              {product.persian_title || "بدون عنوان"}
            </Link>

            <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-[11px] text-muted-foreground">
              {product.brand_name && <span>برند: {product.brand_name}</span>}
              {product.category_name && <span className="truncate">دسته: {product.category_name}</span>}
            </div>

            <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
              <span className="inline-flex items-center gap-1 text-[11px] text-muted-foreground">
                <Store className="h-3 w-3" aria-hidden />
                {formatNumber(product.shops_count)} فروشگاه
              </span>
              {!product.has_specs && (
                <span className="inline-flex items-center gap-1 rounded-md border border-border bg-muted px-1.5 py-0.5 text-[11px] text-muted-foreground">
                  <AlertCircle className="h-3 w-3" aria-hidden />
                  مشخصات ثبت نشده
                </span>
              )}
            </div>

            <div className="mt-2">
              {hasPrice ? (
                <>
                  <div className="text-[10px] text-muted-foreground">کمترین قیمت ثبت‌شده</div>
                  <div className="text-sm font-bold leading-6 text-primary sm:text-base">
                    {formatCompactToman(product.min_price_toman)}
                  </div>
                </>
              ) : (
                <div className="text-xs font-medium text-muted-foreground">قیمتی ثبت نشده</div>
              )}
            </div>

            <div className="mt-1.5 flex flex-wrap gap-1.5">
                <Button asChild size="sm" variant="outline" className="h-8 text-xs">
                  <Link href={`/product/${product.product_id}`}>
                    جزئیات
                    <ArrowLeft className="mr-1 h-3 w-3" aria-hidden />
                  </Link>
                </Button>
                {onSelect && (
                  <Button
                    size="sm"
                    className="h-8 text-xs"
                    onClick={() => onSelect(product)}
                  >
                    فروشگاه‌ها
                  </Button>
                )}
            </div>
          </div>
        </div>

        {product.match_reasons?.length > 0 && (
          <ul className="mt-2 flex flex-wrap gap-1 border-t pt-2">
            {product.match_reasons.slice(0, 3).map((r, i) => (
              <li
                key={i}
                className="rounded bg-secondary px-1.5 py-0.5 text-[10px] text-secondary-foreground"
              >
                {r}
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
