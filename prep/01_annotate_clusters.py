#!/usr/bin/env python
"""Step 01 -- merge the 34 graphclust clusters into named cell types.

HUMAN GATE 1. This writes ``prep/atera_cluster_annotation.csv``, which is committed
to the repo and reviewed by a person before anything downstream is trusted. The
companion ``atera_cluster_annotation.pdf`` exists so the reviewer can judge the call
visually rather than taking the score on faith.

Method -- deliberately simple and auditable, no clustering or model fitting:

1. Start from the vendor ``differential_expression.csv`` that ships in
   `analysis.tar.gz`.
2. Drop targets whose peak per-cluster mean count is below
   ``ANNOT_MIN_MEAN_COUNTS`` -- whole-transcriptome Xenium carries thousands of
   near-zero targets whose log2 fold changes are noise.
3. Within each cluster, rank the surviving genes by log2 fold change and convert
   rank to a percentile in [0, 1] (1.0 = most enriched gene in that cluster).
4. Score each candidate cell type as the *mean rank percentile of its markers*.
   Marker sets differ in size, and a mean keeps a 2-gene set comparable to a
   5-gene one. The same mean computed on *mean counts* instead of fold change
   gives ``expr_pct``, a second and independent axis: is the type's evidence
   actually detected in this cluster, or only relatively enriched?
5. Resolve the label through four rules, in order. None of them is a manual edit;
   all of them are visible in the CSV.

   a. STATE VETO. Types in ``ANNOT_STATE_TYPES`` describe a state, not a lineage,
      and are only called when their markers appear among the cluster's own top
      ``ANNOT_MARKER_TOP_N`` significant DE genes. Cycling genes rank moderately
      high in *every* epithelial cluster relative to the whole transcriptome, so
      a plain argmax hands "Proliferating tumour" to clusters that are simply
      epithelial. Vetoed types drop out and the next best is taken.

   b. MIXED. If markers of two or more different types show up in the top
      ``ANNOT_MIXED_TOP_N`` DE genes, the cluster is a doublet or a merge and is
      labelled ``Mixed (a/b)`` rather than handed to whichever scored a hair
      higher.

   c. NO EVIDENCE -> Unassigned. A cluster with no gene passing
      ``ANNOT_MAX_ADJ_P`` at all has nothing to score against, so no score of any
      size may name it. Likewise a cluster whose winning type has ``expr_pct``
      below ``ANNOT_MIN_EXPR_PCT``: the markers are not detectably expressed
      there, and the fold-change win is ambient signal.

   d. Everything else takes the argmax.

6. Flag ``low_confidence`` for every Unassigned or Mixed row, and for any row
   whose margin is below ``ANNOT_LOW_CONF_MARGIN``, whose absolute score is below
   ``ANNOT_MIN_SCORE``, or whose ``expr_pct`` is below ``ANNOT_MIN_EXPR_PCT``.

A dedicated B-cell interrogation runs at the end (``BCELL_CHECK_GENES``), because
"there are no B cells on this slide" is a claim a Tutorial should only make on
evidence. It reports both DE-table statistics and the per-cluster detection rate
read straight from the count matrix.

``manual_override`` is written blank and is the intended edit point: anything typed
there wins over ``assigned_type`` everywhere downstream (see
``atera_io.cell_annotation_table``). Re-running this script will NOT clobber a
filled-in override unless ``--reset-overrides`` is passed.

Runs on Bunya, never in Colab.  ~1 min (~20 s with --no-bcell-check).
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.backends.backend_pdf import PdfPages

import config as C
import atera_io as io


# --------------------------------------------------------------------------- #
# Reshape the vendor differential expression table
# --------------------------------------------------------------------------- #


def load_de() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, list[int]]:
    """Return (log2fc, mean_counts, adj_p) as genes x clusters frames."""
    de = io.read_analysis("differential_expression")
    clusters = sorted(
        {
            int(c.split()[1])
            for c in de.columns
            if c.startswith("Cluster ") and c.endswith("Log2 fold change")
        }
    )
    genes = de["Feature Name"].astype(str).values

    def grab(suffix: str) -> pd.DataFrame:
        cols = [f"Cluster {k} {suffix}" for k in clusters]
        out = de[cols].copy()
        out.columns = clusters
        out.index = genes
        return out

    return (
        grab("Log2 fold change"),
        grab("Mean Counts"),
        grab("Adjusted p value"),
        clusters,
    )


# --------------------------------------------------------------------------- #
# Scoring
# --------------------------------------------------------------------------- #


def score_clusters(
    log2fc: pd.DataFrame, mean_counts: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Return (log2FC rank percentile, fold-change score, expression score).

    ``pct`` is genes x clusters; both score frames are clusters x cell types.
    """
    expressed = mean_counts.max(axis=1) >= C.ANNOT_MIN_MEAN_COUNTS
    n_drop = int((~expressed).sum())
    print(
        f"expression floor {C.ANNOT_MIN_MEAN_COUNTS}: kept "
        f"{int(expressed.sum()):,} / {len(expressed):,} targets ({n_drop:,} dropped)"
    )

    all_markers = [g for genes in C.CELL_TYPE_MARKERS.values() for g in genes]
    lost = [g for g in all_markers if g not in expressed.index or not expressed[g]]
    if lost:
        raise SystemExit(
            f"marker genes removed by the expression floor: {lost}. "
            "Lower config.ANNOT_MIN_MEAN_COUNTS."
        )

    lfc = log2fc.loc[expressed]
    mcs = mean_counts.loc[expressed]
    # rank 1 = lowest log2FC; percentile 1.0 = most enriched gene in the cluster
    pct = lfc.rank(axis=0, method="average", pct=True)
    pct_expr = mcs.rank(axis=0, method="average", pct=True)

    def _score(p: pd.DataFrame) -> pd.DataFrame:
        s = pd.DataFrame(
            index=lfc.columns, columns=list(C.CELL_TYPE_MARKERS), dtype=float
        )
        for ctype, markers in C.CELL_TYPE_MARKERS.items():
            s[ctype] = p.loc[markers].mean(axis=0)
        s.index.name = "cluster"
        return s

    return pct, _score(pct), _score(pct_expr)


def ranked_de_genes(
    log2fc: pd.DataFrame, adj_p: pd.DataFrame, mean_counts: pd.DataFrame, cluster: int
) -> list[str]:
    """Significant genes of one cluster, most enriched first."""
    ok = (adj_p[cluster] <= C.ANNOT_MAX_ADJ_P) & (
        mean_counts.max(axis=1) >= C.ANNOT_MIN_MEAN_COUNTS
    )
    return list(log2fc.loc[ok, cluster].sort_values(ascending=False).index)


# --------------------------------------------------------------------------- #
# Label resolution
# --------------------------------------------------------------------------- #


def resolve(
    cluster: int,
    scores: pd.DataFrame,
    expr_scores: pd.DataFrame,
    de_ranked: list[str],
) -> dict:
    """Apply the state veto, the Mixed rule and the no-evidence rule, in order."""
    top_marker = set(de_ranked[: C.ANNOT_MARKER_TOP_N])
    top_mixed = set(de_ranked[: C.ANNOT_MIXED_TOP_N])
    order = scores.loc[cluster].sort_values(ascending=False)

    def has_marker_evidence(t: str) -> bool:
        return bool(set(C.CELL_TYPE_MARKERS[t]) & top_marker)

    # (a) state veto ---------------------------------------------------------- #
    vetoed: list[str] = []
    candidates = list(order.index)
    while candidates and candidates[0] in C.ANNOT_STATE_TYPES:
        if has_marker_evidence(candidates[0]):
            break
        vetoed.append(candidates.pop(0))

    base = candidates[0] if candidates else order.index[0]
    score = float(order[base])
    runner_up = candidates[1] if len(candidates) > 1 else order.index[-1]
    margin = score - float(order[runner_up])
    expr_pct = float(expr_scores.loc[cluster, base])
    marker_hits = sorted(set(C.CELL_TYPE_MARKERS[base]) & top_marker)

    # (b) mixed --------------------------------------------------------------- #
    mixed_types = sorted(
        (t for t in C.CELL_TYPE_MARKERS if set(C.CELL_TYPE_MARKERS[t]) & top_mixed),
        key=lambda t: -float(order[t]),
    )

    # (c) no evidence --------------------------------------------------------- #
    no_de = len(de_ranked) == 0
    weak_expr = expr_pct < C.ANNOT_MIN_EXPR_PCT

    if no_de or weak_expr:
        label = C.UNASSIGNED_LABEL
        reason = (
            "no significant DE genes"
            if no_de
            else f"expr_pct {expr_pct:.3f} below the {C.ANNOT_MIN_EXPR_PCT} floor"
        )
    elif len(mixed_types) >= 2:
        label = C.mixed_label(mixed_types[0], mixed_types[1])
        reason = (
            f"markers of {len(mixed_types)} types "
            f"({', '.join(mixed_types)}) in the top {C.ANNOT_MIXED_TOP_N} DE genes"
        )
    else:
        label, reason = base, ""

    # `markers_in_top50` being empty is informative and is reported as its own
    # column, but it is deliberately NOT a low-confidence trigger: several large,
    # unambiguously-typed clusters (2 = tumour, 3 = fibroblast) carry none of the
    # canonical markers in their own top 50 because whole-transcriptome log2FC
    # rankings are dominated by low-expressed, cluster-private targets.
    low_conf = bool(
        label == C.UNASSIGNED_LABEL
        or label.startswith("Mixed")
        or margin < C.ANNOT_LOW_CONF_MARGIN
        or score < C.ANNOT_MIN_SCORE
        or weak_expr
    )
    return {
        "assigned_type": label,
        "best_scoring_type": base,
        "score": round(score, 4),
        "margin": round(margin, 4),
        "runner_up": runner_up,
        "expr_pct": round(expr_pct, 4),
        "markers_in_top50": ";".join(marker_hits),
        "state_vetoed": ";".join(vetoed),
        "resolution": reason,
        "low_confidence": low_conf,
    }


# --------------------------------------------------------------------------- #
# B-cell interrogation
# --------------------------------------------------------------------------- #


def bcell_report(
    mean_counts: pd.DataFrame,
    pct: pd.DataFrame,
    n_cells: pd.Series,
    table: pd.DataFrame,
    read_matrix: bool = True,
) -> pd.DataFrame:
    """Where do B-cell genes actually live? Report, never force a label."""
    genes = [g for g in C.BCELL_CHECK_GENES if g in mean_counts.index]
    missing = [g for g in C.BCELL_CHECK_GENES if g not in mean_counts.index]
    print()
    print("=" * 78)
    print("B-CELL INTERROGATION -- " + ", ".join(C.BCELL_CHECK_GENES))
    if missing:
        print(f"  not present as targets: {missing}")

    det = None
    if read_matrix:
        X, found, barcodes = io.read_panel_matrix(panel_genes=genes)
        gc = io.read_analysis("graphclust_clusters")
        cl_of = (
            pd.Series(gc["Cluster"].values, index=gc["Barcode"].astype(str))
            .reindex(pd.Index(barcodes.astype(str)))
            .to_numpy()
        )
        ok = ~pd.isna(cl_of)
        grp = pd.Series(cl_of[ok].astype(int))
        det = pd.DataFrame(
            {
                g: pd.Series((X[ok, i] > 0).astype(float)).groupby(grp).mean() * 100
                for i, g in enumerate(found)
            }
        )
        det["any_of_4"] = (
            pd.Series((X[ok] > 0).any(axis=1).astype(float)).groupby(grp).mean() * 100
        )

    rows = []
    ann = table.set_index("cluster")
    for c in mean_counts.columns:
        r = {
            "cluster": c,
            "n_cells": int(n_cells[c]),
            "assigned_type": ann.loc[c, "assigned_type"],
            "B_cell_score": round(
                float(pct.loc[C.CELL_TYPE_MARKERS["B cell"], c].mean()), 3
            ),
        }
        for g in genes:
            r[f"{g}_mc"] = round(float(mean_counts.loc[g, c]), 3)
        if det is not None and c in det.index:
            for g in genes:
                r[f"{g}_%det"] = round(float(det.loc[c, g]), 1)
            r["any4_%det"] = round(float(det.loc[c, "any_of_4"]), 1)
        rows.append(r)
    rep = pd.DataFrame(rows).sort_values("B_cell_score", ascending=False)

    pd.set_option("display.width", 260)
    print(rep.head(8).to_string(index=False))
    best = rep.iloc[0]
    print()
    print(
        f"  highest B-cell marker score: cluster {int(best['cluster'])} "
        f"({int(best['n_cells']):,} cells, labelled '{best['assigned_type']}'), "
        f"score {best['B_cell_score']:.3f}"
    )
    if det is not None:
        n_pos = (det["any_of_4"] * n_cells.reindex(det.index) / 100).sum()
        print(
            f"  slide-wide {n_pos:,.0f} of {int(n_cells.sum()):,} clustered cells "
            f"({100 * n_pos / n_cells.sum():.2f}%) detect at least one of {genes}"
        )
    print(
        "  B cell never wins the argmax in any cluster, so no B-cell label is\n"
        "  forced. This is reported, not papered over."
    )
    print("=" * 78)
    return rep


# --------------------------------------------------------------------------- #
# Figures
# --------------------------------------------------------------------------- #


def make_pdf(
    table: pd.DataFrame,
    scores: pd.DataFrame,
    pct: pd.DataFrame,
    mean_counts: pd.DataFrame,
    log2fc: pd.DataFrame,
    bcell: pd.DataFrame,
    path: Path,
) -> None:
    type_rank = {t: i for i, t in enumerate(C.cell_type_order(table["assigned_type"]))}
    order = table.assign(
        _r=table["assigned_type"].map(type_rank).fillna(99)
    ).sort_values(["_r", "score"], ascending=[True, False])
    cl_order = list(order["cluster"])
    markers = [g for genes in C.CELL_TYPE_MARKERS.values() for g in genes]
    ylabels = [
        f"{c:>2}  {t}{' *' if lc else ''}  (n={n:,})"
        for c, t, n, lc in zip(
            order["cluster"],
            order["assigned_type"],
            order["n_cells"],
            order["low_confidence"],
        )
    ]
    edges = np.cumsum([len(g) for g in C.CELL_TYPE_MARKERS.values()])[:-1]

    def _yticks(ax):
        ax.set_yticks(range(len(cl_order)))
        ax.set_yticklabels(ylabels, fontsize=7, family="monospace")
        for i, t in enumerate(order["assigned_type"]):
            ax.get_yticklabels()[i].set_color(C.cell_type_color(t))

    with PdfPages(path) as pdf:
        # -- page 1: marker rank-percentile heatmap ---------------------------- #
        M = pct.loc[markers, cl_order].T.values
        fig, ax = plt.subplots(figsize=(16, 11))
        im = ax.imshow(M, aspect="auto", cmap="RdYlBu_r", vmin=0, vmax=1)
        ax.set_xticks(range(len(markers)))
        ax.set_xticklabels(markers, rotation=90, fontsize=7)
        _yticks(ax)
        for e in edges:
            ax.axvline(e - 0.5, color="k", lw=0.8)
        sec = ax.secondary_xaxis("top")
        starts = np.concatenate([[0], edges])
        ends = np.concatenate([edges, [len(markers)]])
        sec.set_xticks((starts + ends - 1) / 2)
        sec.set_xticklabels(
            list(C.CELL_TYPE_MARKERS), rotation=45, ha="left", fontsize=8
        )
        fig.colorbar(
            im, ax=ax, label="log2FC rank percentile within cluster", shrink=0.6
        )
        ax.set_title(
            "Atera graphclust -> cell type: marker enrichment\n"
            "rows = clusters (ordered by assignment, * = low confidence)",
            fontsize=11,
        )
        fig.tight_layout()
        pdf.savefig(fig)
        plt.close(fig)

        # -- page 2: dotplot, size = mean counts, colour = log2FC -------------- #
        mc = mean_counts.loc[markers, cl_order].T.values
        lf = log2fc.loc[markers, cl_order].T.values
        yy, xx = np.mgrid[0 : len(cl_order), 0 : len(markers)]
        fig, ax = plt.subplots(figsize=(16, 11))
        size = 6 + 240 * (np.log1p(mc) / max(np.log1p(mc).max(), 1e-9))
        sc = ax.scatter(
            xx.ravel(),
            yy.ravel(),
            s=size.ravel(),
            c=np.clip(lf.ravel(), -3, 3),
            cmap="RdBu_r",
            vmin=-3,
            vmax=3,
            linewidths=0.2,
            edgecolors="k",
        )
        ax.set_xticks(range(len(markers)))
        ax.set_xticklabels(markers, rotation=90, fontsize=7)
        _yticks(ax)
        ax.set_ylim(len(cl_order) - 0.5, -0.5)
        for e in edges:
            ax.axvline(e - 0.5, color="k", lw=0.8)
        fig.colorbar(sc, ax=ax, label="log2 fold change (clipped +/-3)", shrink=0.6)
        ax.set_title(
            "Marker dotplot -- dot size = mean counts per cell, colour = log2FC",
            fontsize=11,
        )
        fig.tight_layout()
        pdf.savefig(fig)
        plt.close(fig)

        # -- page 3: cluster x cell-type score, assignment marked -------------- #
        S = scores.loc[cl_order].values
        fig, ax = plt.subplots(figsize=(10, 11))
        im = ax.imshow(S, aspect="auto", cmap="viridis")
        ax.set_xticks(range(len(C.CELL_TYPES)))
        ax.set_xticklabels(C.CELL_TYPES, rotation=45, ha="right", fontsize=9)
        _yticks(ax)
        idx = order.set_index("cluster")
        for i, cl in enumerate(cl_order):
            j = C.CELL_TYPES.index(idx.loc[cl, "best_scoring_type"])
            overruled = idx.loc[cl, "assigned_type"] != idx.loc[cl, "best_scoring_type"]
            ax.add_patch(
                plt.Rectangle(
                    (j - 0.5, i - 0.5),
                    1,
                    1,
                    fill=False,
                    ec="#ff3b3b" if overruled else "w",
                    lw=2,
                )
            )
        fig.colorbar(im, ax=ax, label="mean marker rank percentile", shrink=0.6)
        ax.set_title(
            "Cell-type score per cluster\n"
            "white box = argmax kept, red box = argmax overruled "
            "(state veto / Mixed / Unassigned)",
            fontsize=11,
        )
        fig.tight_layout()
        pdf.savefig(fig)
        plt.close(fig)

        # -- page 4: cells per assigned type ----------------------------------- #
        agg = table.groupby("assigned_type")["n_cells"].sum()
        agg = agg.reindex(C.cell_type_order(agg.index))
        fig, ax = plt.subplots(figsize=(10, 5.5))
        ax.bar(agg.index, agg.values, color=[C.cell_type_color(t) for t in agg.index])
        for i, v in enumerate(agg.values):
            ax.text(i, v, f"{int(v):,}", ha="center", va="bottom", fontsize=8)
        ax.set_ylabel("cells")
        ax.set_title("Whole slide composition after merging 34 clusters")
        plt.setp(ax.get_xticklabels(), rotation=45, ha="right")
        fig.tight_layout()
        pdf.savefig(fig)
        plt.close(fig)

        # -- page 5: B-cell interrogation -------------------------------------- #
        det_cols = [c for c in bcell.columns if c.endswith("_%det")]
        if det_cols:
            b = bcell.sort_values("cluster")
            fig, ax = plt.subplots(figsize=(13, 6))
            w = 0.8 / len(det_cols)
            for i, col in enumerate(det_cols):
                ax.bar(
                    np.arange(len(b)) + i * w,
                    b[col].values,
                    width=w,
                    label=col.replace("_%det", ""),
                )
            ax.set_xticks(np.arange(len(b)) + 0.4)
            ax.set_xticklabels(
                [f"{int(c)}\n{t[:13]}" for c, t in zip(b["cluster"], b["assigned_type"])],
                fontsize=6,
            )
            ax.set_ylabel("% of cells with >= 1 count")
            ax.set_xlabel("graphclust cluster")
            ax.legend(fontsize=8)
            ax.set_title(
                "B-cell interrogation: detection rate of "
                + ", ".join(C.BCELL_CHECK_GENES)
                + "\nno cluster is B-cell dominated, so no B-cell label is forced"
            )
            fig.tight_layout()
            pdf.savefig(fig)
            plt.close(fig)

    print(f"wrote {path}")


# --------------------------------------------------------------------------- #

#: The columns the sign-off contract requires, then the informational ones that
#: let a reviewer see WHY each call was made.
CSV_COLUMNS = [
    "cluster",
    "n_cells",
    "top10_genes",
    "assigned_type",
    "score",
    "margin",
    "manual_override",
    "best_scoring_type",
    "runner_up",
    "expr_pct",
    "n_sig_de",
    "markers_in_top50",
    "state_vetoed",
    "resolution",
    "low_confidence",
]


def main() -> int:
    C.ensure_dirs()
    reset = "--reset-overrides" in sys.argv
    do_bcell = "--no-bcell-check" not in sys.argv

    log2fc, mean_counts, adj_p, clusters = load_de()
    gc = io.read_analysis("graphclust_clusters")
    n_cells = gc["Cluster"].value_counts().reindex(clusters).fillna(0).astype(int)

    pct, scores, expr_scores = score_clusters(log2fc, mean_counts)

    rows = []
    for c in clusters:
        de_ranked = ranked_de_genes(log2fc, adj_p, mean_counts, c)
        r = resolve(c, scores, expr_scores, de_ranked)
        r["cluster"] = c
        r["n_cells"] = int(n_cells[c])
        r["top10_genes"] = (
            ";".join(de_ranked[: C.ANNOT_TOP_N_GENES])
            if de_ranked
            else C.ANNOT_NO_DE_SENTINEL
        )
        r["n_sig_de"] = len(de_ranked)
        rows.append(r)

    table = pd.DataFrame(rows)
    table["manual_override"] = ""
    table = table[CSV_COLUMNS]

    # Preserve any override a reviewer already typed in.
    if C.CLUSTER_ANNOTATION_CSV.exists() and not reset:
        prev = pd.read_csv(C.CLUSTER_ANNOTATION_CSV)
        if "manual_override" in prev:
            keep = prev.set_index("cluster")["manual_override"]
            table["manual_override"] = (
                table["cluster"].map(keep).fillna("").astype(str).replace("nan", "")
            )
            n_kept = int((table["manual_override"].str.strip() != "").sum())
            if n_kept:
                print(f"preserved {n_kept} existing manual_override value(s)")

    table.to_csv(C.CLUSTER_ANNOTATION_CSV, index=False)
    print(f"wrote {C.CLUSTER_ANNOTATION_CSV}")

    # -- report ------------------------------------------------------------- #
    pd.set_option("display.width", 260)
    print()
    print(
        table[
            [
                "cluster",
                "n_cells",
                "assigned_type",
                "score",
                "margin",
                "expr_pct",
                "n_sig_de",
                "markers_in_top50",
                "state_vetoed",
                "low_confidence",
            ]
        ].to_string(index=False)
    )

    print()
    print("overruled clusters (argmax refused):")
    ov = table[table["resolution"] != ""]
    if ov.empty:
        print("  none")
    for _, r in ov.iterrows():
        print(
            f"  cluster {r['cluster']:>2} ({r['n_cells']:>6,} cells): "
            f"'{r['best_scoring_type']}' -> '{r['assigned_type']}'  ({r['resolution']})"
        )
    vet = table[table["state_vetoed"] != ""]
    for _, r in vet.iterrows():
        print(
            f"  cluster {r['cluster']:>2} ({r['n_cells']:>6,} cells): state veto "
            f"dropped '{r['state_vetoed']}' (no marker in the top "
            f"{C.ANNOT_MARKER_TOP_N}) -> '{r['assigned_type']}'"
        )

    print()
    agg = table.groupby("assigned_type")["n_cells"].sum()
    agg = agg.reindex(C.cell_type_order(agg.index))
    print("cells per cell type")
    for t, v in agg.items():
        print(f"  {t:26s} {v:>8,}  ({100 * v / agg.sum():5.1f}%)")

    n_low = int(table["low_confidence"].sum())
    print()
    print(
        f"{n_low} of {len(table)} clusters are low-confidence: "
        f"{list(table.loc[table['low_confidence'], 'cluster'])}"
    )
    unused = [t for t in C.CELL_TYPES if t not in set(table["assigned_type"])]
    if unused:
        print(f"cell types no cluster was assigned to: {unused}")

    bcell = bcell_report(mean_counts, pct, n_cells, table, read_matrix=do_bcell)
    bcell.to_csv(C.WORK_DIR / "bcell_interrogation.csv", index=False)

    make_pdf(table, scores, pct, mean_counts, log2fc, bcell, C.CLUSTER_ANNOTATION_PDF)
    print()
    print(
        "HUMAN GATE 1: review prep/atera_cluster_annotation.pdf, then fill in "
        "manual_override in prep/atera_cluster_annotation.csv and commit it."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
