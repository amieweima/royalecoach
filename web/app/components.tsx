"use client";

import { useEffect, useState } from "react";
import { API_URL, CardMeta } from "@/lib/api";

export function useApi<T>(path: string) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let alive = true;
    fetch(`${API_URL}${path}`)
      .then(async (r) => {
        if (!r.ok) throw new Error((await r.json()).detail ?? r.statusText);
        return r.json();
      })
      .then((d) => alive && setData(d))
      .catch((e) => alive && setError(String(e.message ?? e)));
    return () => {
      alive = false;
    };
  }, [path]);
  return { data, error };
}

const RARITY_VAR: Record<string, string> = {
  common: "var(--rarity-common)",
  rare: "var(--rarity-rare)",
  epic: "var(--rarity-epic)",
  legendary: "var(--rarity-legendary)",
  champion: "var(--rarity-champion)",
};

/* Official card art with a rarity-colored ring, like the game's card frames. */
export function CardChip({ name, meta, size = 30 }: { name: string; meta?: CardMeta; size?: number }) {
  if (!meta?.icon) return null;
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={meta.icon}
      alt=""
      className="card-chip"
      style={{
        height: size,
        borderColor: RARITY_VAR[meta.rarity?.toLowerCase() ?? ""] ?? "var(--rarity-common)",
      }}
      loading="lazy"
    />
  );
}

export function Section({
  eyebrow,
  title,
  note,
  children,
}: {
  eyebrow: string;
  title: string;
  note?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="card p-6 md:p-8">
      <p className="eyebrow">{eyebrow}</p>
      <h2 className="display text-2xl font-semibold mt-1 mb-1">{title}</h2>
      {note && <p className="text-sm mb-4" style={{ color: "var(--ink-2)" }}>{note}</p>}
      <div className="mt-4">{children}</div>
    </section>
  );
}

/* A diverging row bar anchored on a center baseline: red grows left (worse /
   pushes losses), blue grows right (better / pushes wins). Values are direct
   labels; the row doubles as the table view. */
export function DeltaRow({
  label,
  sub,
  value,
  valueLabel,
  maxAbs,
  leading,
}: {
  label: string;
  sub?: string;
  value: number;
  valueLabel: string;
  maxAbs: number;
  leading?: React.ReactNode;
}) {
  const frac = maxAbs > 0 ? Math.min(Math.abs(value) / maxAbs, 1) : 0;
  const positive = value >= 0;
  return (
    <div className="grid items-center gap-3 py-1.5" style={{ gridTemplateColumns: "minmax(150px, 1fr) 2fr 72px" }}>
      <div className="min-w-0 flex items-center gap-2">
        {leading}
        <div className="min-w-0">
          <span className="text-sm font-medium truncate block">{label}</span>
          {sub && <span className="text-xs" style={{ color: "var(--muted)" }}>{sub}</span>}
        </div>
      </div>
      <div className="relative h-4" role="img" aria-label={`${label}: ${valueLabel}`}>
        <div className="absolute inset-y-0 left-1/2 w-px" style={{ background: "var(--baseline)" }} />
        <div
          className="absolute inset-y-0.5"
          style={{
            left: positive ? "50%" : `${50 - frac * 50}%`,
            width: `${frac * 50}%`,
            background: positive ? "var(--you)" : "var(--them)",
            borderRadius: positive ? "0 4px 4px 0" : "4px 0 0 4px",
          }}
        />
      </div>
      <span className="tab-nums text-sm text-right font-medium">{valueLabel}</span>
    </div>
  );
}

/* A single-measure rate bar (win rate 0-100%) with a reference tick at the
   overall rate, so every number is read against the baseline it should be. */
export function RateRow({
  label,
  sub,
  rate,
  reference,
}: {
  label: string;
  sub?: string;
  rate: number | null;
  reference: number;
}) {
  return (
    <div className="grid items-center gap-3 py-1.5" style={{ gridTemplateColumns: "minmax(150px, 1fr) 2fr 72px" }}>
      <div className="min-w-0">
        <span className="text-sm font-medium block truncate">{label}</span>
        {sub && <span className="text-xs" style={{ color: "var(--muted)" }}>{sub}</span>}
      </div>
      <div
        className="relative h-4 rounded"
        style={{ background: "var(--paper)" }}
        role="img"
        aria-label={`${label}: ${rate == null ? "no data" : Math.round(rate * 100) + "%"}`}
      >
        {rate != null && (
          <div
            className="absolute inset-y-0.5 left-0"
            style={{
              width: `${rate * 100}%`,
              background: "var(--you)",
              borderRadius: "0 4px 4px 0",
            }}
          />
        )}
        <div
          className="absolute -inset-y-0.5 w-0.5"
          style={{ left: `${reference * 100}%`, background: "var(--ink)" }}
          title={`overall ${Math.round(reference * 100)}%`}
        />
      </div>
      <span className="tab-nums text-sm text-right font-medium">
        {rate == null ? "—" : `${Math.round(rate * 100)}%`}
      </span>
    </div>
  );
}

export function StatTile({
  label,
  value,
  sub,
  accent = "var(--gold)",
}: {
  label: string;
  value: string;
  sub?: string;
  accent?: string;
}) {
  return (
    <div className="card px-5 py-4 overflow-hidden relative">
      <div className="absolute inset-x-0 top-0 h-1" style={{ background: accent }} />
      <p className="eyebrow">{label}</p>
      <p className="display text-3xl font-semibold mt-1">{value}</p>
      {sub && <p className="text-xs mt-1" style={{ color: "var(--muted)" }}>{sub}</p>}
    </div>
  );
}
