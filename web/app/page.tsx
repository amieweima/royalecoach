"use client";

import {
  CardIndex,
  CoachReport,
  GlobalInsights,
  Matchup,
  Stats,
  featureLabel,
  pct,
} from "@/lib/api";
import { CardChip, DeltaRow, RateRow, Section, StatTile, useApi } from "./components";

function pickVerdict(coach: CoachReport): Matchup | null {
  const losing = coach.worst_matchups.filter((m) => m.delta_vs_overall < 0);
  if (!losing.length) return null;
  // weight severity by sample size so a 2-battle fluke can't headline
  return losing.reduce((worst, m) =>
    m.delta_vs_overall * Math.sqrt(m.n) < worst.delta_vs_overall * Math.sqrt(worst.n) ? m : worst
  );
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
  const { data: stats, error: statsError } = useApi<Stats>("/stats");
  const { data: coach, error: coachError } = useApi<CoachReport>("/coach");
  const { data: insights, error: insightsError } =
    useApi<GlobalInsights>("/insights/global");
  const { data: cards } = useApi<CardIndex>("/cards");

  const overall = coach?.overall.win_rate ?? 0.5;
  const verdict = coach ? pickVerdict(coach) : null;
  const maxDelta = coach
    ? Math.max(...coach.worst_matchups.map((m) => Math.abs(m.delta_vs_overall)), 0.01)
    : 1;
  const maxShap = insights
    ? Math.max(...insights.top_features.map((f) => f.importance), 0.0001)
    : 1;
  const maxUnder = coach
    ? Math.max(...coach.underleveled_cards.map((c) => c.underlevel), 1)
    : 1;

  if (statsError) {
    return (
      <main className="max-w-3xl mx-auto px-6 py-24">
        <h1 className="display text-3xl font-semibold mb-3" style={{ color: "var(--on-arena)" }}>
          ClashCoach
        </h1>
        <div className="card p-6">
          <p className="font-medium mb-1">The API isn&apos;t reachable.</p>
          <p className="text-sm" style={{ color: "var(--ink-2)" }}>
            Start it from <code>api/</code> with{" "}
            <code>python -m uvicorn app.main:app --reload</code>, then reload
            this page.
          </p>
        </div>
      </main>
    );
  }

  return (
    <main className="max-w-4xl mx-auto px-6 py-10 flex flex-col gap-6">
      <header className="flex items-baseline justify-between flex-wrap gap-2">
        <h1 className="display text-2xl font-bold tracking-tight" style={{ color: "var(--on-arena)" }}>
          Clash<span style={{ color: "var(--gold)" }}>Coach</span>
        </h1>
        <p className="text-xs tab-nums" style={{ color: "var(--on-arena-2)" }}>
          {stats?.last_battle
            ? `latest battle banked ${new Date(stats.last_battle + "Z").toLocaleString()}`
            : "loading…"}
        </p>
      </header>

      {/* The coach's verdict: the single most damning finding, as a sentence. */}
      <section className="py-6 on-arena" style={{ color: "var(--on-arena)" }}>
        <p className="eyebrow">
          <span style={{ color: "var(--gold)" }}>★</span> scouting report · verdict
        </p>
        {coachError ? (
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
                Decks with {verdict.card} are beating you.
              </h2>
              <p className="mt-3 text-base max-w-2xl" style={{ color: "var(--on-arena-2)" }}>
                You win{" "}
                <strong className="tab-nums" style={{ color: "var(--on-arena)" }}>
                  {pct(verdict.win_rate)}
                </strong>{" "}
                of battles when the opponent runs {verdict.card} ({verdict.n}{" "}
                battles) — against your {pct(overall)} overall. That gap is the
                first thing to train.
              </p>
            </div>
            {cards?.[verdict.card]?.icon && (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={cards[verdict.card].icon!}
                alt={verdict.card}
                className="h-32 w-auto drop-shadow-lg"
                style={{ transform: "rotate(3deg)" }}
              />
            )}
          </div>
        ) : (
          <h2 className="display text-5xl font-semibold mt-2 leading-tight">
            {coach ? "No standout weakness yet — keep banking battles." : "Reading your history…"}
          </h2>
        )}
      </section>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatTile label="Your battles" value={String(stats?.battles.me ?? "—")} sub="banked by the poller" accent="var(--gold)" />
        <StatTile label="Win rate" value={pct(coach?.overall.win_rate)} sub={coach ? `${coach.overall.wins} wins` : undefined} accent="var(--you)" />
        <StatTile label="Sessions" value={String(coach?.tilt.sessions ?? "—")} sub="30-min gap = new session" accent="var(--rarity-epic)" />
        <StatTile label="Training set" value={(stats?.battles.ladder ?? 0).toLocaleString()} sub="top-ladder battles harvested" accent="var(--rarity-rare)" />
      </div>

      {coach && (
        <>
          <Section
            eyebrow="matchups"
            title="Where you lose"
            note={`Win rate vs. your ${pct(overall)} overall when the opponent's deck contains each card. Only cards seen in ≥5 battles.`}
          >
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
          </Section>

          <Section
            eyebrow="tilt"
            title="Momentum and session length"
            note="Win rate by situation, read against the black tick — your overall rate. Small samples are honest samples; the n is on every row."
          >
            <RateRow label="After a win" sub={`${coach.tilt.after_win.n} battles`} rate={coach.tilt.after_win.win_rate} reference={overall} />
            <RateRow label="After a loss" sub={`${coach.tilt.after_loss.n} battles`} rate={coach.tilt.after_loss.win_rate} reference={overall} />
            <RateRow label="After two straight losses" sub={`${coach.tilt.after_two_losses.n} battles`} rate={coach.tilt.after_two_losses.win_rate} reference={overall} />
            <div className="my-2 border-t" style={{ borderColor: "var(--hairline)" }} />
            <RateRow label="Battles 1–5 of a session" sub={`${coach.tilt.session_battles_1_to_5.n} battles`} rate={coach.tilt.session_battles_1_to_5.win_rate} reference={overall} />
            <RateRow label="Battle 6 onward" sub={`${coach.tilt.session_battles_6_plus.n} battles`} rate={coach.tilt.session_battles_6_plus.win_rate} reference={overall} />
          </Section>

          {coach.underleveled_cards.length > 0 && (
            <Section
              eyebrow="card levels"
              title="Your upgrade queue"
              note="How far below max level each card in your decks sits. Levels are the one weakness you can fix without changing how you play."
            >
              {coach.underleveled_cards.slice(0, 10).map((c) => (
                <div
                  key={c.card}
                  className="grid items-center gap-3 py-1.5"
                  style={{ gridTemplateColumns: "minmax(150px, 1fr) 2fr 72px" }}
                >
                  <span className="text-sm font-medium truncate flex items-center gap-2">
                    <CardChip name={c.card} meta={cards?.[c.card]} />
                    {c.card}
                  </span>
                  <div className="relative h-4 rounded" style={{ background: "var(--paper)" }}>
                    <div
                      className="absolute inset-y-0.5 left-0"
                      style={{
                        width: `${(c.underlevel / maxUnder) * 100}%`,
                        background: "var(--you-deep)",
                        borderRadius: "0 4px 4px 0",
                      }}
                    />
                  </div>
                  <span className="tab-nums text-sm text-right font-medium">
                    −{c.underlevel} lvl
                  </span>
                </div>
              ))}
            </Section>
          )}
        </>
      )}

      <Section
        eyebrow="the model"
        title="What decides top-ladder battles"
        note={
          insights
            ? `SHAP feature attributions from the win-probability model, over ${insights.n_battles.toLocaleString()} harvested battles. Honest finding: at top ladder every deck is viable, so deck features alone beat a coin flip only slightly — outcomes are mostly skill.`
            : insightsError
              ? "No trained model found — run `python -m app.ml.train` in api/."
              : "Computing SHAP attributions… (this one takes a few seconds)"
        }
      >
        {insights && (
          <>
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
