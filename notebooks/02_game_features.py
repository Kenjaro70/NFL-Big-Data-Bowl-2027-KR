# %% [markdown]
# # Phase 2 — game cut features and outcomes
#
# Runs the Phase 1 cut detector on every regular-season WR route, validates it
# against route semantics, builds per-player game cut features and NFL outcomes,
# and measures how reliable each one is. Writes:
#
# - `data/features/game_cuts.parquet`            one row per scored route break
# - `data/features/game_player_features.parquet` one row per WR (all seasons, and rookie season)
# - `data/features/route_outcomes.parquet`       one row per WR route
# - `data/features/player_outcomes.parquet`      one row per WR, with draft and career info
# - `reports/02_game_features.md` + `reports/figures/02_*.png`
#
# Measurement only: nothing here relates combine features to game features or
# outcomes. Those are Phase 3's pre-registered tests.
#
# Run: `python notebooks/02_game_features.py`

# %%
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from src import cuts as C  # noqa: E402
from src import features as F  # noqa: E402
from src import game as G  # noqa: E402
from src import outcomes as O  # noqa: E402
from src.data import connect  # noqa: E402
from src.report import Report  # noqa: E402
from src.viz import INK, INK2, SERIES, SURFACE, use_style  # noqa: E402

FEATURES = ROOT / "data" / "features"
FIGURES = ROOT / "reports" / "figures"
FEATURES.mkdir(parents=True, exist_ok=True)
FIGURES.mkdir(parents=True, exist_ok=True)
MIN_ROUTES = 100  # "qualified" WR: enough REG routes for stable player-level numbers (Phase 0)

con = connect()
rep = Report("Phase 2 — game cut features and outcomes", "notebooks/02_game_features.py")
use_style()

rep.section("Method")
rep.text(
    "- **Routes:** every regular-season route run by a player who did the WR drills at the combine. "
    "Cut features use routes with a throw; outcomes use all routes.",
    "- **Cuts:** the Phase 1 detector (`src/cuts.py`), unchanged. A break counts if its apex falls between the "
    "snap and the throw; kinematics use 0.5 s before the snap to 1 s after the throw so breaks near either edge "
    "are measurable.",
    "- **Features:** each metric is z-scored within its slot (route type × turn direction × order, the game "
    "version of the combine's drill slots) after a linear adjustment for the break's turn angle (as in the "
    "combine) and for play design: break depth (and its square), alignment (wide/slot/other), man vs zone "
    "coverage, and pre-snap motion. Player features average those z-scores over all seasons, and over the "
    "rookie season alone, which every draft class has exactly once.",
    "- **Outcomes** are per-route rates. Separation over expected (SOE) compares each route with cohort routes "
    "of the same type against the same coverage family (man/zone) from the same alignment (wide/slot).",
    f"- **Qualified WRs** have ≥ {MIN_ROUTES} regular-season routes; reliability is measured on them.",
)

# %% [markdown]
# ## 1. Routes and windows

# %%
ro = O.route_outcomes(con)
rts = G.routes(con)
rts["route_id"] = rts[G.KEY].astype(str).agg("_".join, axis=1)
players = con.sql("""SELECT p.nfl_id, p.display_name, p.draft_year, p.draft_overall_pick, p.nfl_position
                     FROM players p JOIN combine_results c USING (nfl_id)
                     WHERE c.combine_position = 'WR'""").df().set_index("nfl_id")

multi_snap = con.sql("""SELECT count(*) FROM (
    SELECT 1 FROM game_tracking_reg t JOIN player_play_reg pp USING (game_id, play_id, nfl_id)
    JOIN combine_results c USING (nfl_id)
    WHERE c.combine_position = 'WR' AND pp.route_ran IS NOT NULL AND t.event = 'ball_snap'
    GROUP BY t.game_id, t.play_id, t.nfl_id HAVING count(*) > 1)""").fetchone()[0]
rep.check("routes with two snap events are rare (< 0.1%) and dropped", multi_snap / len(ro) < 0.001,
          f"{multi_snap} of {len(ro):,} routes")

by_season = pd.DataFrame({
    "all routes": ro.groupby("season").size(),
    "with a throw and tracking": rts.groupby("season").size(),
})
by_season.loc["total"] = by_season.sum()
rep.section("Routes by season", by_season, index=True,
            note=f"{ro.nfl_id.nunique()} WRs ran at least one regular-season route. Routes without a throw "
                 "(sacks, scrambles) count for outcomes but have no break window.")
rep.check("≥ 85% of WR routes have a throw and tracking",
          len(rts) / len(ro) >= 0.85, f"{len(rts):,} of {len(ro):,} ({len(rts) / len(ro):.0%})")

frames = G.route_frames(con, rts)
sample = frames.merge(rts[G.KEY].sample(3000, random_state=0), on=G.KEY)
err = np.concatenate([np.abs(C.kinematics(r.x.to_numpy(), r.y.to_numpy())["speed"] - r.s.to_numpy())
                      for _, r in sample.groupby(G.KEY)])
rep.check("smoothed speed matches the provided `s` in game tracking", np.median(err) < 0.1,
          f"median |diff| {np.median(err):.3f} yd/s over 3,000 routes")

# %% [markdown]
# ## 2. Breaks detected on game routes

# %%
cuts = G.route_cuts(frames, rts)
first = cuts.sort_values("t_apex").groupby("route_id").first()
det = rts.assign(has_cut=rts.route_id.isin(cuts.route_id))
tab = det.groupby("route_ran").agg(routes=("route_id", "size"), with_break=("has_cut", "mean"),
                                   throw_s=("throw_s", "median"))
tab["first_break_s"] = first.groupby("route_ran").t_apex.median()
tab["first_break_deg"] = first.groupby("route_ran").turn_deg.median()
late = det.throw_s >= det.route_ran.map(tab.first_break_s) + 0.5
tab["with_break_if_thrown_late"] = det[late].groupby("route_ran").has_cut.mean()
tab = tab.sort_values("routes", ascending=False)
rep.section(
    "Breaks detected, by route type", tab, index=True,
    note="`with_break` is the share of routes with at least one break between the snap and the throw. Many routes "
         "are thrown before their break (often to another receiver), so the last column restricts to throws at "
         "least 0.5 s after the route type's median break time. Hitches stop rather than turn, and go routes "
         "have no designed break.")

wide = first[first.inside.notna()]
sem = wide.groupby("route_ran").inside.agg(routes="size", inside="mean")
sem = sem.reindex([r for r in G.INSIDE_ROUTES + G.OUTSIDE_ROUTES if r in sem.index])
sem["expected"] = ["inside" if r in G.INSIDE_ROUTES else "outside" for r in sem.index]
sem["share matching"] = np.where(sem.expected == "inside", sem.inside, 1 - sem.inside)
rep.section(
    "First break direction vs route type (WRs lined up wide)", sem.drop(columns="inside"), index=True,
    note=f"Players more than {G.WIDE_MARGIN:.0f} yd from the field's center line, where their side of the ball is "
         "unambiguous. Slants, ins, posts and crosses should break toward the middle; outs, corners and flats "
         "toward the sideline. Agreement confirms the left/right sign on game data.")
rep.check("first break goes the expected way (inside/outside) for ≥ 75% of each route type",
          (sem["share matching"] >= 0.75).all(),
          ", ".join(f"{r.lower()} {v:.0%}" for r, v in sem["share matching"].items()))

# %% [markdown]
# ## 3. Game cut features

# %%
fc = cuts.join(players[["draft_year"]], on="nfl_id")
z = F.slot_z(fc, by_direction=True, base="route_ran", rep="route_id", covariates=G.COVARIATES)
slot_tab = z.groupby("slot").agg(
    cuts=("route_id", "size"), players=("nfl_id", "nunique"), apex_s=("t_apex", "median"),
    turn_deg=("turn_deg", "median"), entry_speed=("entry_speed", "median"), apex_speed=("apex_speed", "median"),
    retention=("speed_retention", "median"), lat_accel=("peak_lat_accel", "median"),
).sort_values("cuts", ascending=False)
rep.section("Game slots (medians)", slot_tab, index=True,
            note=f"{len(z):,} of {len(fc):,} breaks fall in slots with ≥ {F.MIN_CUTS_PER_SLOT} breaks. "
                 "Speeds in yd/s, accelerations in yd/s², apex time in s after the snap.")

feats = F.player_features(z, "game", unit="game_id", unit_label="games").join(
    F.player_features(z[z.season == z.draft_year], "game_rookie", unit="game_id", unit_label="games"), how="outer")

# %% [markdown]
# ## 4. Outcomes

# %%
po = O.player_outcomes(ro).join(O.player_outcomes(ro[ro.season == ro.draft_year], prefix="rookie_"), how="outer")
qualified = po.index[po.routes >= MIN_ROUTES]
has_sep = ro.separation.notna()
rep.check("every route with separation has an expected separation", ro.loc[has_sep, "expected_separation"].notna().all())
rep.check("separation over expected averages ~0 across routes", abs(ro.loc[has_sep, "soe"].mean()) < 0.05,
          f"mean {ro.loc[has_sep, 'soe'].mean():+.3f} yd")
cov = ro[has_sep].groupby("coverage").separation.mean()
rep.text(f"Raw separation averages {cov.get('ZONE_COVERAGE', np.nan):.2f} yd against zone and "
         f"{cov.get('MAN_COVERAGE', np.nan):.2f} yd against man, which is why SOE conditions on coverage.")

# %% [markdown]
# ## 5. Reliability: game features and outcomes (qualified WRs, split by game)

# %%
rel = F.split_half_reliability(z[z.nfl_id.isin(qualified)], n_iter=200, unit="game_id", min_units=4)
kind = {"": "mean", "_lr": "left − right", "_sd": "consistency (SD)"}
rel["metric"] = rel.feature.str.replace(r"_(lr|sd)$", "", regex=True)
rel["kind"] = rel.feature.str.extract(r"(_lr|_sd)$")[0].fillna("").map(kind)
rel_tab = rel.pivot(index="metric", columns="kind", values="reliability").loc[list(F.METRICS), list(kind.values())]
qf = feats.loc[feats.index.isin(qualified)]
rel_tab.insert(0, "median cuts", qf.game_n_cuts.median())
rep.section(
    "Split-half reliability of game cut features", rel_tab, index=True,
    note=f"{rel.players.iloc[0]} qualified WRs with ≥ 4 games; each player's games are split at random, "
         "median over 200 splits, Spearman–Brown corrected.")
PRIMARY = ["entry_speed", "speed_retention", "peak_lat_accel"]
rep.text(
    "**Game-side reliability is moderate, not high.** PLAN.md assumed the many game reps would make game "
    "features stable; with a median of " + f"{qf.game_n_cuts.median():.0f}" + " scored breaks per qualified WR, the "
    "pre-registered features reach " + ", ".join(f"{m} {rel_tab.loc[m, 'mean']:.2f}" for m in PRIMARY) + ". "
    "A threshold of 0.7 set before this run was not met. Breaks vary with the play call and the defense far "
    "more than combine reps do, even after the adjustments above.",
    "The scoring (which covariates, which routes) was chosen by comparing about six variants on this "
    "reliability alone, never on outcomes or combine links, so these values are slightly optimistic.",
)

orel = O.outcome_reliability(ro[ro.nfl_id.isin(qualified)], n_iter=200).set_index("outcome")
q = po.loc[qualified, list(O.OUTCOMES)]
out_tab = pd.DataFrame({
    "description": pd.Series(O.OUTCOME_LABELS),
    "p25": q.quantile(0.25), "median": q.median(), "p75": q.quantile(0.75),
    "reliability": orel.reliability,
}).rename_axis("outcome")
rep.section("Outcomes for qualified WRs", out_tab, index=True,
            note=f"{len(qualified)} WRs with ≥ {MIN_ROUTES} routes; reliability splits each player's games in half. "
                 "Catch rate and YAC over expected rest on targets and catches only, so they are the noisiest.")

# %% [markdown]
# ## 6. Exposure by draft class

# %%
exp = players.join(po[["routes", "targets"]]).join(feats[["game_n_cuts"]])
exp_tab = exp.groupby("draft_year").agg(
    wrs=("display_name", "size"), with_routes=("routes", "count"),
    qualified=("routes", lambda s: int((s >= MIN_ROUTES).sum())),
    median_routes_qualified=("routes", lambda s: s[s >= MIN_ROUTES].median()),
)
exp_tab["median_breaks_qualified"] = exp[exp.routes >= MIN_ROUTES].groupby("draft_year").game_n_cuts.median()
rep.section("Exposure by draft class", exp_tab, index=True,
            note="The 2025 class has one season, so few of its WRs qualify. Rookie-season features and outcomes "
                 "put every class on the same footing.")

# %% [markdown]
# ## 7. Figure: detected breaks on game routes

# %%
ROUTE_PANELS = ["SLANT", "IN", "POST", "CROSS", "OUT", "CORNER", "FLAT", "HITCH"]
rng = np.random.default_rng(3)
wide_ids = first[first.inside.notna()].reset_index()
fig, axes = plt.subplots(2, 4, figsize=(14, 8.2), sharex=True, sharey=True)
for ax, route in zip(axes.ravel(), ROUTE_PANELS):
    ids = wide_ids.loc[wide_ids.route_ran == route, "route_id"].to_numpy()
    for col, rid in zip(SERIES, rng.choice(ids, 3, replace=False)):
        rt = rts.loc[rts.route_id == rid].iloc[0]
        rr = frames[(frames.game_id == rt.game_id) & (frames.play_id == rt.play_id) & (frames.nfl_id == rt.nfl_id)
                    & (frames.time >= rt.snap) & (frames.time <= rt.pass_forward)]
        side = np.sign(G.CENTER_Y - rt.y_snap)               # +1: middle of the field is toward +y
        fwd = 1 if rt.play_direction == "right" else -1
        px, py = (rr.y.to_numpy() - rt.y_snap) * side, (rr.x.to_numpy() - rt.x_snap) * fwd
        ax.plot(px, py, color=col, lw=1.6)
        for t in cuts.loc[cuts.route_id == rid, "apex_time"]:
            i = int(np.argmin(np.abs((rr.time - t).dt.total_seconds().to_numpy())))
            ax.plot(px[i], py[i], "o", ms=8, mfc=SURFACE, mec=col, mew=1.5)
    ax.set_title(route.title(), loc="left")
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlim(-12, 12)
    ax.set_ylim(-3, 21)
for ax in axes[1]:
    ax.set_xlabel("yards toward the middle of the field →")
for ax in axes[:, 0]:
    ax.set_ylabel("yards downfield")
fig.suptitle("Detected breaks (circles) on three random routes per type, snap to throw, WRs lined up wide",
             x=0.01, ha="left", color=INK, fontsize=11)
fig.text(0.01, 0.005, "Every route starts at (0, 0); the middle of the field is to the right in every panel.",
         color=INK2, fontsize=8)
fig.tight_layout(rect=(0, 0.02, 1, 1))
fig.savefig(FIGURES / "02_game_breaks.png", dpi=90)
plt.close(fig)
rep.section("Figure")
rep.text("![Detected breaks on game routes](figures/02_game_breaks.png)")

# %%
z.to_parquet(FEATURES / "game_cuts.parquet", index=False)
feats.to_parquet(FEATURES / "game_player_features.parquet")
ro.to_parquet(FEATURES / "route_outcomes.parquet", index=False)
career = con.sql("SELECT * FROM player_career_successes").df().set_index("nfl_id")
players.join(po, how="inner").join(career).to_parquet(FEATURES / "player_outcomes.parquet")
rep.write(ROOT / "reports" / "02_game_features.md")
print(f"\n{len(rep.checks)} checks passed; {len(feats)} WRs with game features; {len(qualified)} qualified")
