import Image from "next/image";
import { cn } from "@ai-cio/utils";
import { BRAND } from "@/lib/brand";

export function BrandLogo({ className }: { className?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-2.5", className)}>
      <Image src={BRAND.mark} width={44} height={44} alt="" priority className="shrink-0 rounded-[13px]" />
      <span className="block">
        <span className="block text-[25px] font-semibold leading-none tracking-[-0.055em] text-[var(--aic-navy)]">
          {BRAND.name}
        </span>
        <span className="mt-1 block text-[10px] font-medium leading-4 tracking-[0.025em] text-slate-500">
          Powered by <span className="font-semibold text-slate-700">{BRAND.provider}</span>
        </span>
      </span>
    </span>
  );
}
