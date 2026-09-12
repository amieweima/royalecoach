"use client";

import {
  CardIndex,
  CoachReport,
  DeckCard,
  GlobalInsights,
  Matchup,
  Stats,
  featureLabel,
  pct,
} from "@/lib/api";
import { useEffect, useState } from "react";
import { CardChip, DeltaRow, Emote, Section, StatTile, useApi } from "./components";

const RARITY_ORDER: Record<string, number> = {
  common: 0,
  rare: 1,
  epic: 2,
  legendary: 3,
  champion: 4,
};

const RARITY_RING: Record<string, string> = {
  common: "var(--rarity-common)",
  rare: "var(--rarity-rare)",
  epic: "var(--rarity-epic)",
  legendary: "var(--rarity-legendary)",
  champion: "var(--rarity-champion)",
};

/* Upgrade order: biggest level deficit first (largest stat handicap), and
   within a tie, cheapest rarity first — commons close a level for a fraction
   of what an epic costs, so they're the fastest win rate available. */
function upgradeRanking(deck: DeckCard[], cards?: CardIndex) {
  const ranked = deck
    .filter((c) => c.underlevel > 0)
    .map((c) => ({
      ...c,
      rarity: cards?.[c.card]?.rarity?.toLowerCase() ?? "common",
    }))
    .sort(
      (a, b) =>
        b.underlevel - a.underlevel ||
        (RARITY_ORDER[a.rarity] ?? 0) - (RARITY_ORDER[b.rarity] ?? 0)
    );
  return ranked.map((c, i) => {
    const gap =
      i > 0 && ranked[i - 1].underlevel === c.underlevel
        ? `also ${c.underlevel} below max`
        : c.underlevel > 1
          ? `${c.underlevel} levels below max — the biggest stat handicap in your deck`
          : `1 level from max`;
    const cost =
      c.rarity === "common"
        ? "a common, so it's the cheapest win rate you can buy"
        : c.rarity === "rare"
          ? "a rare — still cheap to level"
          : c.rarity === "epic"
            ? "an epic — pricier, but the stat jump is real"
            : `a ${c.rarity} — expensive, queue it after the cheap wins`;
    return { ...c, reason: `${gap}, and it's ${cost}.` };
  });
}

type Verdict =
  | { kind: "archetype"; cards: string[]; n: number; win_rate: number }
  | { kind: "card"; card: string; n: number; win_rate: number };

function pickVerdict(coach: CoachReport): Verdict | null {
  // Prefer the archetype view: "bait decks beat you" is the real story, while
  // per-card stats are confounded by staples that sit in half the meta.
  const archetypes = (coach.worst_archetypes ?? []).filter(
    (a) => a.delta_vs_overall < -0.05
  );
  if (archetypes.length) {
    const worst = archetypes.reduce((w, a) =>
      a.delta_vs_overall * Math.sqrt(a.n) < w.delta_vs_overall * Math.sqrt(w.n) ? a : w
    );
    return { kind: "archetype", ...worst };
  }
  const losing = coach.worst_matchups.filter((m) => m.delta_vs_overall < 0);
  if (!losing.length) return null;
  // weight severity by sample size so a 2-battle fluke can't headline
  const worst = losing.reduce((w, m) =>
    m.delta_vs_overall * Math.sqrt(m.n) < w.delta_vs_overall * Math.sqrt(w.n) ? m : w
  );
  return { kind: "card", ...worst };
}

/* Translate SHAP rankings into findings a player can use. Order is the
   insight: what matters most, next, and (pointedly) least. */
function modelFindings(ins: GlobalInsights): string[] {
  const feats = ins.top_features;
  const trophy = feats.find((f) => f.feature === "trophy_diff");
  const underlevel = feats.find((f) => f.feature.includes("underlevel"));
  const topCard = feats.find((f) => f.feature.includes("::"));
  const findings: string[] = [];
  if (trophy)
    findings.push(
      "Rating gap decides most: the higher-rated player usually wins, and no deck choice comes close to outweighing it."
    );
  if (underlevel)
    findings.push(
      "Card levels are the next biggest edge — an underleveled deck loses games it should win. (That's your upgrade queue above.)"
    );
  if (trophy && topCard) {
    const ratio = Math.round(trophy.importance / topCard.importance);
    findings.push(
      `No single card dominates. The strongest card signal (${topCard.feature.slice(3)}) matters ~${ratio}× less than rating — the meta is balanced, so skill and levels beat deck-switching.`
    );
  }
  return findings;
}

/* The game plan: every insight the coach has, converted into a ranked list
   of actions with the evidence attached. Ordered by the size of the gap each
   one addresses. */
function gamePlan(
  coach: CoachReport,
  cards: CardIndex | undefined,
  overall: number
): { action: string; why: string }[] {
  const plan: { action: string; why: string }[] = [];

  const arch = coach.worst_archetypes?.[0];
  if (arch && arch.delta_vs_overall < -0.05)
    plan.push({
      action: `Learn the ${arch.cards[0]} matchup`,
      why: `You win ${pct(arch.win_rate)} against decks built around ${arch.cards
        .slice(0, 3)
        .join(" · ")} (${arch.n} battles) vs your ${pct(overall)} average — the biggest hole in your results. Watch how top players defend it, or run it yourself in friendlies to learn its rhythm.`,
    });

  const early = coach.tilt.session_battles_1_to_5;
  const late = coach.tilt.session_battles_6_plus;
  if (late.win_rate != null && late.n >= 5) {
    const earlyRate = early.win_rate ?? overall;
    if (late.win_rate <= earlyRate - 0.1)
      plan.push({
        action: "Keep sessions to about 5 battles",
        why: `You win ${pct(earlyRate)} in battles 1–5 of a session but only ${pct(late.win_rate)} from battle 6 on. Stop while you're fresh and bank the trophies.`,
      });
    else if (late.win_rate >= earlyRate + 0.1)
      plan.push({
        action: "Play longer sessions",
        why: `You warm up: ${pct(late.win_rate)} from battle 6 on vs ${pct(earlyRate)} early. Your best play comes after you've settled in.`,
      });
  }

  const ranking = upgradeRanking(coach.deck ?? [], cards);
  if (ranking.length)
    plan.push({
      action: `Put your next gold into ${ranking[0].card}`,
      why: `It's ${ranking[0].reason.replace(/\.$/, "")} — and the model ranks card levels as the #2 win factor on ladder.`,
    });

  const t2 = coach.tilt.after_two_losses;
  if (t2.win_rate != null && t2.n >= 5) {
    if (t2.win_rate >= overall + 0.1)
      plan.push({
        action: "Don't quit after a losing streak",
        why: `You win ${pct(t2.win_rate)} of battles right after two straight losses (${t2.n} so far) — streaks don't rattle you, so keep queuing when others would tilt.`,
      });
    else if (t2.win_rate <= overall - 0.1)
      plan.push({
        action: "Walk away after two straight losses",
        why: `Your win rate collapses to ${pct(t2.win_rate)} after two losses in a row. Two is your stop signal.`,
      });
  }

  return plan;
}

function Legend({ negative, positive }: { negative: string; positive: string }) {
  return (
    <div className="flex gap-4 text-xs mb-2" style={{ color: "var(--ink-2)" }}>
      <span className="flex items-center gap-1.5">
        <span className="inline-block w-3 h-3 rounded-sm" style={{ background: "var(--them)" }} />
        {negative}
      </span>
      <span className="flex items-center gap-1.5">
        <span className="inline-block w-3 h-3 rounded-sm" style={{ background: "var(--you)" }} />
        {positive}
      </span>
    </div>
  );
}

export default function Home() {
  // A typed-in tag switches the whole report to that player, fetched live.
  const [tag, setTag] = useState<string | null>(null);
  const [tagInput, setTagInput] = useState("");
  useEffect(() => {
    const fromUrl = new URLSearchParams(window.location.search).get("tag");
    if (fromUrl) {
      setTag(fromUrl);
      setTagInput(fromUrl);
    }
  }, []);
  const scout = (next: string | null) => {
    setTag(next);
    setTagInput(next ?? "");
    window.history.replaceState(
      null,
      "",
      next ? `?tag=${encodeURIComponent(next)}` : window.location.pathname
    );
  };

  const { data: stats, error: statsError } = useApi<Stats>("/stats");
  const { data: coach, error: coachError } = useApi<CoachReport>(
    tag ? `/coach/${encodeURIComponent(tag)}` : "/coach"
  );
  const { data: insights, error: insightsError } =
    useApi<GlobalInsights>("/insights/global");
  const { data: cards } = useApi<CardIndex>("/cards");
  const scouting = coach?.player ?? null;

  const overall = coach?.overall.win_rate ?? 0.5;
  const verdict = coach ? pickVerdict(coach) : null;
  const maxDelta = coach
    ? Math.max(...coach.worst_matchups.map((m) => Math.abs(m.delta_vs_overall)), 0.01)
    : 1;
  const maxShap = insights
    ? Math.max(...insights.top_features.map((f) => f.importance), 0.0001)
    : 1;

  if (statsError) {
    return (
      <main className="max-w-3xl mx-auto px-6 py-24">
        <h1 className="display text-3xl font-semibold mb-3" style={{ color: "var(--on-arena)" }}>
          RoyaleCoach
        </h1>
        <div className="card p-6">
          <p className="font-medium mb-1">The coach&apos;s server isn&apos;t answering.</p>
          <p className="text-sm" style={{ color: "var(--ink-2)" }}>
            It may just be waking up from a nap — reload this page in a
            minute. (Running locally? Start the API from <code>api/</code>{" "}
            with <code>python -m uvicorn app.main:app --reload</code>.)
          </p>
        </div>
      </main>
    );
  }

  return (
    <main className="max-w-4xl mx-auto px-6 py-10 flex flex-col gap-6">
      <header className="flex items-baseline justify-between flex-wrap gap-2">
        <h1 className="display text-2xl font-bold tracking-tight" style={{ color: "var(--on-arena)" }}>
          Royale<span style={{ color: "var(--gold)" }}>Coach</span>
        </h1>
        <p className="text-xs tab-nums" style={{ color: "var(--on-arena-2)" }}>
          {stats?.last_battle
            ? `latest battle banked ${new Date(stats.last_battle + "Z").toLocaleString()}`
            : "loading…"}
        </p>
      </header>

      {/* Scout any player: a tag swaps the whole report to their live battle log. */}
      <form
        className="flex items-center gap-2 flex-wrap"
        onSubmit={(e) => {
          e.preventDefault();
          scout(tagInput.trim() || null);
        }}
      >
        <input
          value={tagInput}
          onChange={(e) => setTagInput(e.target.value)}
          placeholder="#PLAYERTAG"
          aria-label="Player tag to scout"
          className="rounded-lg px-3 py-2 text-sm font-medium tab-nums"
          style={{
            background: "var(--arena-3)",
            border: "1.5px solid rgba(246, 196, 69, 0.4)",
            color: "var(--on-arena)",
            width: "12rem",
          }}
        />
        <button
          type="submit"
          className="rounded-lg px-4 py-2 text-sm font-bold"
          style={{ background: "var(--gold)", color: "#3a2a00" }}
        >
          Scout
        </button>
        {tag && (
          <button
            type="button"
            onClick={() => scout(null)}
            className="rounded-lg px-3 py-2 text-sm font-medium"
            style={{
              background: "var(--arena-3)",
              border: "1.5px solid rgba(246, 196, 69, 0.4)",
              color: "var(--on-arena-2)",
            }}
          >
            ✕ back to my report
          </button>
        )}
        <span className="text-xs" style={{ color: "var(--on-arena-2)" }}>
          {scouting
            ? `scouting ${scouting.name} ${scouting.tag} · last ${coach?.overall.n} battles`
            : "enter your player tag (in your profile, under your name) for your own scouting report"}
        </span>
      </form>

      {/* Main display: your battle deck, styled like the game's deck screen,
          with the upgrade priority built in. */}
      {coach?.deck && coach.deck.length > 0 && (
        <section
          className="rounded-2xl overflow-hidden"
          style={{
            background: "var(--arena-3)",
            border: "2px solid rgba(246, 196, 69, 0.55)",
          }}
        >
          <div className="px-5 md:px-6 pt-5 flex items-baseline justify-between flex-wrap gap-2">
            <h2 className="display text-2xl font-bold" style={{ color: "var(--gold)" }}>
              Battle Deck
            </h2>
            <span className="text-xs" style={{ color: "var(--on-arena-2)" }}>
              {scouting
                ? `from ${scouting.name}'s latest battle`
                : "from your latest ladder battle"}
            </span>
          </div>

          <div className="grid grid-cols-4 gap-2 md:gap-3 px-5 md:px-6 py-4">
            {coach.deck.map((c) => {
              const meta = cards?.[c.card];
              const maxed = c.underlevel === 0;
              return (
                <div
                  key={c.card}
                  className="relative rounded-lg overflow-hidden"
                  style={{
                    background: "var(--arena-2)",
                    border: `2px solid ${RARITY_RING[meta?.rarity?.toLowerCase() ?? "common"] ?? "var(--rarity-common)"}`,
                  }}
                >
                  {meta?.icon && (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={meta.icon} alt={c.card} className="w-full h-auto block" />
                  )}
                  {meta?.elixir != null && (
                    <span
                      className="absolute top-1 left-1 w-6 h-6 rounded-full flex items-center justify-center text-sm font-bold"
                      style={{
                        background: "#b34fd3",
                        color: "#fff",
                        border: "1.5px solid #fff",
                        textShadow: "0 1px 2px rgba(0,0,0,0.5)",
                      }}
                    >
                      {meta.elixir}
                    </span>
                  )}
                  <div
                    className="text-center text-xs font-bold py-1"
                    style={{
                      background: maxed ? "var(--gold)" : "var(--arena-1)",
                      color: maxed ? "#3a2a00" : "var(--on-arena)",
                    }}
                  >
                    Level {c.level}
                    {!maxed && (
                      <span style={{ opacity: 0.75 }}> · −{c.underlevel}</span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>

          {(() => {
            const costs = coach.deck
              .map((c) => cards?.[c.card]?.elixir)
              .filter((e): e is number => e != null);
            if (!costs.length) return null;
            const avg = costs.reduce((a, b) => a + b, 0) / costs.length;
            return (
              <p
                className="text-center text-sm font-semibold pb-4 flex items-center justify-center gap-1.5"
                style={{ color: "var(--on-arena)" }}
              >
                <svg width="12" height="16" viewBox="0 0 12 16" aria-hidden="true">
                  <path
                    d="M6 0 C6 0 0 8 0 11 a6 5 0 0 0 12 0 C12 8 6 0 6 0Z"
                    fill="#b34fd3"
                  />
                </svg>
                Average elixir cost: {avg.toFixed(1)}
              </p>
            );
          })()}

          {(() => {
            const ranking = upgradeRanking(coach.deck, cards ?? undefined);
            if (!ranking.length) return null;
            return (
              <div
                className="px-5 md:px-6 pb-5 pt-4"
                style={{ borderTop: "1px solid rgba(246, 196, 69, 0.25)" }}
              >
                <p className="eyebrow" style={{ color: "var(--gold)" }}>
                  upgrade next
                </p>
                <ol className="m-0 mt-2 pl-0 list-none flex flex-col gap-2">
                  {ranking.map((c, i) => (
                    <li key={c.card} className="flex items-center gap-3">
                      <span
                        className="display font-bold tab-nums w-5 text-right"
                        style={{ color: "var(--gold)" }}
                      >
                        {i + 1}
                      </span>
                      <CardChip name={c.card} meta={cards?.[c.card]} size={34} />
                      <span className="text-sm" style={{ color: "var(--on-arena)" }}>
                        <strong>{c.card}</strong>{" "}
                        <span style={{ color: "var(--on-arena-2)" }}>— {c.reason}</span>
                      </span>
                    </li>
                  ))}
                </ol>
              </div>
            );
          })()}
        </section>
      )}

      {/* The coach's verdict: the single most damning finding, as a sentence. */}
      <section className="py-6 on-arena" style={{ color: "var(--on-arena)" }}>
        <p className="eyebrow">
          <span style={{ color: "var(--gold)" }}>★</span> scouting report · verdict
        </p>
        {coachError && tag ? (
          <>
            <h2 className="display text-5xl font-semibold mt-2 leading-tight">
              Couldn&apos;t scout that tag.
            </h2>
            <p className="mt-3 text-base max-w-2xl" style={{ color: "var(--on-arena-2)" }}>
              {coachError} Tags are in your profile under your name, like
              #C8LVVCVJJ.
            </p>
          </>
        ) : coachError ? (
          <>
            <h2 className="display text-5xl font-semibold mt-2 leading-tight">
              No battles banked yet.
            </h2>
            <p className="mt-3 text-base" style={{ color: "var(--on-arena-2)" }}>
              Run the poller, play a few matches, and the coach will have
              something to say.
            </p>
          </>
        ) : verdict ? (
          <div className="flex items-center gap-6 flex-wrap">
            <div className="min-w-0 flex-1" style={{ minWidth: "260px" }}>
              <h2 className="display text-5xl font-semibold mt-2 leading-tight">
                {verdict.kind === "archetype"
                  ? `${verdict.cards[0]} decks are beating you.`
                  : `Decks with ${verdict.card} are beating you.`}
              </h2>
              <p className="mt-3 text-base max-w-2xl" style={{ color: "var(--on-arena-2)" }}>
                You win{" "}
                <strong className="tab-nums" style={{ color: "var(--on-arena)" }}>
                  {pct(verdict.win_rate)}
                </strong>{" "}
                {verdict.kind === "archetype"
                  ? `against decks built around ${verdict.cards.slice(0, 3).join(" · ")}`
                  : `of battles when the opponent runs ${verdict.card}`}{" "}
                ({verdict.n} battles) — against your {pct(overall)} overall.
                That gap is the first thing to train.
              </p>
            </div>
            <div className="flex items-end gap-2">
              <Emote mood="crying-king" size={88} />
              {(verdict.kind === "archetype" ? verdict.cards.slice(0, 3) : [verdict.card]).map(
                (name, i) =>
                  cards?.[name]?.icon && (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                      key={name}
                      src={cards[name].icon!}
                      alt={name}
                      className="h-24 w-auto drop-shadow-lg"
                      style={{ transform: `rotate(${(i - 1) * 5}deg)` }}
                    />
                  )
              )}
            </div>
          </div>
        ) : (
          <h2 className="display text-5xl font-semibold mt-2 leading-tight">
            {coach
              ? "No standout weakness yet — keep banking battles."
              : tag
                ? "Pulling that player's battle log…"
                : "Reading your history…"}
          </h2>
        )}
      </section>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatTile
          label="Your battles"
          value={String(coach?.overall.n ?? (tag ? "—" : (stats?.battles.me ?? "—")))}
          sub={scouting ? "from the recent battle log" : "tracked so far — grows as you play"}
          accent="var(--gold)"
        />
        <StatTile
          label="Win rate"
          value={pct(coach?.overall.win_rate)}
          sub={coach ? `${coach.overall.wins} wins · ${coach.overall.n - coach.overall.wins} losses` : undefined}
          accent="var(--you)"
        />
        <StatTile
          label="Sessions"
          value={String(coach?.tilt.sessions ?? "—")}
          sub="separate sittings you've played"
          accent="var(--rarity-epic)"
        />
        <StatTile
          label="AI training set"
          value={(stats?.battles.ladder ?? 0).toLocaleString()}
          sub="top-player battles the model learned from"
          accent="var(--rarity-rare)"
        />
      </div>

      {coach && (
        <>
          <Section
            eyebrow="matchups"
            title="Which decks beat you"
            note="Your opponents' decks, classified into meta archetypes learned from ~12,000 harvested ladder decks — because a popular staple card in every deck says less than the deck it belongs to."
          >
            {(() => {
              const archetypes = coach.worst_archetypes;
              if (!archetypes?.length)
                return (
                  <p className="coach-line">
                    Not enough classified battles yet — keep playing and the
                    deck-type picture fills in.
                  </p>
                );
              const worst = archetypes[0];
              return (
                <>
                  <p className="coach-line">
                    {worst.delta_vs_overall < -0.05
                      ? `Decks built around ${worst.cards.slice(0, 3).join(", ")} are your problem — everything else you handle at or above your average.`
                      : "No deck type stands out as a problem right now."}
                  </p>
                  <div className="flex flex-col gap-3">
                    {archetypes.slice(0, 4).map((a) => {
                      const losing = a.delta_vs_overall < 0;
                      return (
                        <div
                          key={a.cards.join()}
                          className="card p-4 flex items-center gap-4 flex-wrap"
                          style={{ background: "var(--paper)" }}
                        >
                          <div className="flex gap-1.5">
                            {a.cards.slice(0, 4).map((name) => (
                              <CardChip key={name} name={name} meta={cards?.[name]} size={44} />
                            ))}
                          </div>
                          <div className="min-w-0 flex-1">
                            <span className="text-sm font-medium block">
                              {a.cards.slice(0, 3).join(" · ")} decks
                            </span>
                            <span className="text-xs" style={{ color: "var(--muted)" }}>
                              {a.n} battles
                            </span>
                          </div>
                          <div className="text-right">
                            <span className="display text-2xl font-semibold tab-nums block">
                              {pct(a.win_rate)}
                            </span>
                            <span
                              className="text-xs font-medium"
                              style={{ color: losing ? "var(--them)" : "var(--you)" }}
                            >
                              {losing ? "▼ below" : "▲ above"} your average
                            </span>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </>
              );
            })()}
            <details className="receipts mt-4">
              <summary>show per-card matchups</summary>
              <Legend negative="below your overall" positive="above your overall" />
              {coach.worst_matchups.slice(0, 12).map((m) => (
                <DeltaRow
                  key={m.card}
                  label={m.card}
                  sub={`${m.n} battles`}
                  value={m.delta_vs_overall}
                  valueLabel={pct(m.win_rate)}
                  maxAbs={maxDelta}
                  leading={<CardChip name={m.card} meta={cards?.[m.card]} />}
                />
              ))}
            </details>
          </Section>

          <Section
            eyebrow="game plan"
            title="How to win more"
            note="Every insight above, turned into actions — ordered by the size of the gap each one closes."
          >
            {(() => {
              const plan = gamePlan(coach, cards ?? undefined, overall);
              const t2 = coach.tilt.after_two_losses;
              const mood =
                t2.win_rate == null || t2.n < 5
                  ? null
                  : t2.win_rate >= overall - 0.1
                    ? "cool-king"
                    : "angry-king";
              if (!plan.length)
                return (
                  <p className="coach-line">
                    Not enough data for a plan yet — keep playing and check back.
                  </p>
                );
              return (
                <div className="flex items-start gap-4">
                  <ol className="m-0 pl-0 list-none flex flex-col gap-3 flex-1">
                    {plan.map((item, i) => (
                      <li key={item.action} className="flex gap-3">
                        <span
                          className="display font-bold tab-nums text-lg w-5 text-right shrink-0"
                          style={{ color: "var(--gold)" }}
                        >
                          {i + 1}
                        </span>
                        <div>
                          <p className="text-sm font-semibold m-0">{item.action}</p>
                          <p className="text-sm m-0 mt-0.5" style={{ color: "var(--ink-2)" }}>
                            {item.why}
                          </p>
                        </div>
                      </li>
                    ))}
                  </ol>
                  {mood && <Emote mood={mood} size={72} />}
                </div>
              );
            })()}
            <details className="receipts mt-4">
              <summary>show the tilt and session numbers</summary>
              <Legend negative="worse than your overall" positive="better than your overall" />
              {(
                [
                  ["After a win", coach.tilt.after_win],
                  ["After a loss", coach.tilt.after_loss],
                  ["After two straight losses", coach.tilt.after_two_losses],
                  ["Battles 1–5 of a session", coach.tilt.session_battles_1_to_5],
                  ["Battle 6 onward", coach.tilt.session_battles_6_plus],
                ] as const
              ).map(([label, r]) => (
                <DeltaRow
                  key={label}
                  label={label}
                  sub={`${r.n} battles`}
                  value={(r.win_rate ?? overall) - overall}
                  valueLabel={pct(r.win_rate)}
                  maxAbs={0.35}
                />
              ))}
            </details>
          </Section>

        </>
      )}

      <Section
        eyebrow="the model"
        title="What the AI learned from the ladder"
        note={
          insights
            ? `Findings from a win-prediction model trained on ${insights.n_battles.toLocaleString()} top-ladder battles, ranked by how much each factor actually moves the odds.`
            : insightsError
              ? "Couldn't load the model's findings — the coach's server may still be waking up. Refresh in a minute."
              : "Asking the model what it learned… (a few seconds)"
        }
      >
        {insights && (
          <>
            <ol className="m-0 pl-0 list-none flex flex-col gap-2">
              {modelFindings(insights).map((finding, i) => (
                <li key={i} className="coach-line flex gap-3" style={{ margin: 0 }}>
                  <span
                    className="display font-semibold tab-nums"
                    style={{ color: "var(--gold)" }}
                  >
                    {i + 1}
                  </span>
                  <span>{finding}</span>
                </li>
              ))}
            </ol>
            <details className="receipts mt-3">
              <summary>for the curious: the raw model internals</summary>
              <p className="text-xs mb-2" style={{ color: "var(--muted)" }}>
                SHAP attributions — bar length is how strongly each feature
                pulls the model&apos;s prediction on average; direction is which
                way it pulls.
              </p>
              <Legend negative="pushes toward losses" positive="pushes toward wins" />
              {insights.top_features.slice(0, 12).map((f) => (
                <DeltaRow
                  key={f.feature}
                  label={featureLabel(f.feature)}
                  value={f.direction === "wins" ? f.importance : -f.importance}
                  valueLabel={f.importance.toFixed(3)}
                  maxAbs={maxShap}
                />
              ))}
            </details>
          </>
        )}
      </Section>

      <footer className="pb-8 text-xs" style={{ color: "var(--on-arena-2)" }}>
        Built on the official Supercell API · win model: gradient boosting with
        isotonic calibration, evaluated on a time-based split against naive
        baselines
      </footer>
    </main>
  );
}
