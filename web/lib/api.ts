export const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface Stats {
  battles: { ladder?: number; me?: number };
  players_in_frontier: number;
  first_battle: string | null;
  last_battle: string | null;
}

export interface Rate {
  n: number;
  win_rate: number | null;
}

export interface Matchup {
  card: string;
  n: number;
  win_rate: number;
  delta_vs_overall: number;
}

export interface UnderlevelCard {
  card: string;
  underlevel: number;
  n: number;
  win_rate: number;
}

export interface CoachReport {
  overall: { n: number; wins: number; win_rate: number | null };
  worst_matchups: Matchup[];
  underleveled_cards: UnderlevelCard[];
  tilt: {
    sessions: number;
    after_win: Rate;
    after_loss: Rate;
    after_two_losses: Rate;
    session_battles_1_to_5: Rate;
    session_battles_6_plus: Rate;
  };
}

export interface CardMeta {
  icon: string | null;
  rarity: string | null;
  elixir: number | null;
}

export type CardIndex = Record<string, CardMeta>;

export interface ShapFeature {
  feature: string;
  importance: number;
  direction: "wins" | "losses";
}

export interface GlobalInsights {
  n_battles: number;
  top_features: ShapFeature[];
}

/** "p::Hog Rider" -> "Hog Rider (your deck)" */
export function featureLabel(feature: string): string {
  if (feature.startsWith("p::")) return `${feature.slice(3)} — your deck`;
  if (feature.startsWith("o::")) return `${feature.slice(3)} — opponent deck`;
  const names: Record<string, string> = {
    trophy_diff: "Trophy difference",
    p_underlevel_mean: "Your avg card underlevel",
    p_underlevel_max: "Your worst card underlevel",
    o_underlevel_mean: "Opponent avg card underlevel",
    o_underlevel_max: "Opponent worst card underlevel",
    underlevel_mean_diff: "Underlevel gap (you − them)",
  };
  return names[feature] ?? feature;
}

export const pct = (x: number | null | undefined) =>
  x == null ? "—" : `${Math.round(x * 100)}%`;
