/**
 * ASI-FIMSA 2026 Workshop deck.
 *
 * Presenter deck for the two-hour hands-on spatial-omics session: two slides on
 * getting Colab running, then three background slides and four exhibit slides per
 * Tutorial, illustrated with the real
 * figures from the verified headless run (verify/output_he_pushed/, 2026-08-27,
 * 5/5 PASS, 0 errors).
 *
 * Built on the shared QIMR house master so the style cannot drift from the other
 * decks. pptxgenjs is global with NODE_PATH unset, so:
 *
 *   NODE_PATH=/home/uqxtan9/.hermes/node/lib/node_modules node slides/build_deck.js
 *
 * Figure dimensions come from figures/manifest.json (written by extract_figures.py)
 * rather than M.pngSize(), because the dense/photographic figures are JPEG.
 */

const fs = require('fs');
const path = require('path');
const M = require('/home/uqxtan9/.claude/skills/academic-pptx/qimr_master.js');

const { RED, BLACK, GREY, WHITE, FACE, txt } = M;
const PANEL = 'F2F2F2';

const HERE = __dirname;
const FIGDIR = path.join(HERE, 'figures');
const FIGS = JSON.parse(fs.readFileSync(path.join(FIGDIR, 'manifest.json'), 'utf8'));
const OUT = path.join(HERE, 'asi_fimsa_workshop_2026.pptx');

// ---- geometry ---------------------------------------------------------------
// The master's TITLE_POS is 0.80in tall, which two lines of a 24pt action title
// overflow. Draw the title here instead, 0.95in tall, and start the body lower.
const TITLE = { x: 2.23, y: 0.05, w: 11.0, h: 0.95 };
const TITLE_SIZE = 24;
const TOP = 1.22;          // content starts below the title
const CAP_Y = 6.38;        // source citation, clear of the 6.95 footer
const BODY = 18;           // hard floor from the house style

// A figure only earns the full slide width once it is wide enough that a
// side-by-side column would starve it. Below that it goes left, text right.
const WIDE_ASPECT = 2.4;
// figure-left / bullets-right
const TALL_FIG = { x: 0.55, y: TOP + 0.03, w: 7.35, h: 5.02 };
const TALL_TXT = { x: 8.20, y: TOP + 0.06, w: 4.63, h: 4.95 };
// figure-top / bullets-below. The strip is sized for three bullets at 18 pt
// with one wrap; fitCheck() shouts at build time if a slide exceeds it.
const WIDE_FIG = { x: 0.70, y: TOP, w: 11.93, h: 3.20 };
const WIDE_TXT = { x: 0.70, y: 4.58, w: 11.93, h: 1.72 };

const pres = M.newDeck();

/** House content slide with a taller title box than the master's default. */
function slide(title) {
  const s = M.houseSlide(pres, null);
  s.addText(title, {
    ...TITLE, fontFace: FACE, fontSize: TITLE_SIZE,
    bold: true, color: RED, valign: 'middle', margin: 0,
  });
  return s;
}

/**
 * Rough wrapped height of a bulleted body, in inches. Arial averages about
 * 0.50 em per character in mixed case; that is close enough to catch the only
 * defect that matters here, a body running under the source citation.
 */
function fitCheck(where, pos, items, size) {
  const cpl = Math.max(1, Math.floor(pos.w / (0.50 * size / 72)));
  const lines = items.reduce((n, t) => n + Math.max(1, Math.ceil(t.length / cpl)), 0);
  const h = lines * (1.21 * size / 72) + (items.length - 1) * (10 / 72);
  if (h > pos.h) {
    console.warn(`OVERFLOW  ${where}: ~${h.toFixed(2)}in of text in a ${pos.h}in box ` +
                 `(${lines} lines at ${size}pt) -- shorten it`);
  }
}

/** Bulleted body. One run per item, so the bullet actually renders. */
function bullets(s, pos, items, size) {
  s.addText(
    items.map((t, i) => ({
      text: t,
      options: {
        breakLine: i < items.length - 1,
        bullet: { indent: 18 },
        fontFace: FACE, fontSize: size || BODY, color: BLACK,
        paraSpaceAfter: 10,
      },
    })),
    { x: pos.x, y: pos.y, w: pos.w, h: pos.h, valign: 'top', align: 'left', margin: 0, wrap: true }
  );
}

/** Muted source line under the exhibit. */
function caption(s, text) {
  s.addText(text, {
    x: 0.70, y: CAP_Y, w: 11.93, h: 0.26,
    fontFace: FACE, fontSize: 12, color: GREY, valign: 'top', align: 'left', margin: 0,
  });
}

/**
 * Place a figure inside `box`, centred, preserving aspect. One scale factor drives
 * both sides: clamping width and height independently silently distorts the figure.
 */
function figure(s, key, box) {
  const f = FIGS[key];
  if (!f) throw new Error(`no figure "${key}" in manifest.json`);
  const scale = Math.min(box.w / f.w, box.h / f.h);
  const w = f.w * scale, h = f.h * scale;
  s.addImage({
    path: path.join(FIGDIR, f.file),
    x: box.x + (box.w - w) / 2,
    y: box.y + (box.h - h) / 2,
    w, h,
  });
}

/** Exhibit slide: layout picked from the figure's own aspect ratio. */
function exhibit(title, key, items, cap, notes) {
  const s = slide(title);
  const f = FIGS[key];
  const wide = f.w / f.h >= WIDE_ASPECT;
  figure(s, key, wide ? WIDE_FIG : TALL_FIG);
  fitCheck(key, wide ? WIDE_TXT : TALL_TXT, items, BODY);
  bullets(s, wide ? WIDE_TXT : TALL_TXT, items, BODY);
  caption(s, cap);
  s.addNotes(notes);
  return s;
}

/**
 * A row of equal panels: a red tag, a bold heading, a line of detail. Used for the
 * concept slides that have no figure to show -- the four Colab steps, the three
 * halves of a ligand-receptor claim, the parts of a Transformer.
 */
function cardRow(s, items, o) {
  const n = items.length;
  const gap = o.gap === undefined ? 0.26 : o.gap;
  const cw = (11.93 - gap * (n - 1)) / n;
  items.forEach(([tag, head, detail], i) => {
    const x = 0.70 + i * (cw + gap);
    s.addShape(pres.ShapeType.roundRect, {
      x, y: o.y, w: cw, h: o.h,
      fill: { color: PANEL }, line: { color: PANEL }, rectRadius: 0.07,
    });
    s.addText(tag, {
      x: x + 0.18, y: o.y + 0.14, w: cw - 0.36, h: 0.38,
      fontFace: FACE, fontSize: o.tagSize || 18, bold: true, color: RED, valign: 'top', margin: 0,
    });
    s.addText(head, {
      x: x + 0.18, y: o.y + o.headY, w: cw - 0.36, h: o.headH,
      fontFace: FACE, fontSize: o.headSize || 16, bold: true, color: BLACK, valign: 'top', margin: 0,
    });
    s.addText(detail, {
      x: x + 0.18, y: o.y + o.detailY, w: cw - 0.36, h: o.h - o.detailY - 0.16,
      fontFace: FACE, fontSize: o.detailSize || 14, color: BLACK, valign: 'top', margin: 0,
    });
  });
}

/** Native table with a red header row. */
function table(s, rows, opts) {
  const head = rows[0].map((t) => ({
    text: t, options: { bold: true, color: WHITE, fill: { color: RED } },
  }));
  const body = rows.slice(1).map((r) =>
    r.map((t, i) => ({ text: t, options: { bold: i === 0, color: BLACK } })));
  s.addTable([head, ...body], {
    x: opts.x, y: opts.y, w: opts.w, colW: opts.colW,
    fontFace: FACE, fontSize: opts.size || 16, color: BLACK,
    border: { type: 'solid', pt: 1, color: 'D9D9D9' },
    rowH: opts.rowH || 0.46, valign: 'middle', margin: 6,
  });
}

// =============================================================================
// Title
// =============================================================================
{
  const s = M.houseSlide(pres, null);
  s.addText('Spatial omics, hands-on:\none disease, three technologies', {
    x: 0.5, y: 1.55, w: 12.3, h: 1.9,
    fontSize: 40, fontFace: FACE, color: RED, bold: true, align: 'left', valign: 'top',
  });
  s.addText([
    { text: 'Xiao Tan', options: { bold: true, breakLine: true } },
    { text: 'Genomics and Machine Learning Lab', options: { breakLine: true } },
    { text: 'QIMR Berghofer Medical Research Institute', options: { breakLine: true } },
    { text: 'The University of Queensland', options: { breakLine: true } },
  ], {
    x: 0.5, y: 3.95, w: 12.3, h: 1.6,
    fontSize: 18, fontFace: FACE, color: BLACK, align: 'left', valign: 'top',
  });
  s.addText('ASI-FIMSA 2026  ·  two-hour Workshop  ·  everything runs in Google Colab', {
    x: 0.5, y: 5.65, w: 12.3, h: 0.4,
    fontSize: 14, fontFace: FACE, color: GREY, align: 'left', valign: 'top',
  });
  s.addNotes([
    'Open by naming the constraint: you are immunologists, not Python programmers, and nothing here needs installing.',
    'The framing sentence is "one disease, three technologies" -- NOT "the same tissue". These are three different FFPE',
    'breast carcinoma specimens matched by disease and preservation, so a difference between two panels can still be a',
    'difference between two tumours. Say that once here and the caveat is paid for.',
    '',
    'Two hours. Four Tutorials. More material is written than fits, deliberately -- what we do not reach is theirs to finish.',
  ].join('\n'));
}

// =============================================================================
// What the two hours contain
// =============================================================================
{
  const s = slide('Four Tutorials, two hours, one disease seen three ways');
  table(s, [
    ['Notebook', 'What you do', 'Time'],
    ['00 · Setup check', 'Confirms Colab can install the stack and reach the data. Run it at home, not in the room.', '~10 min'],
    ['01 · Read and visualise', 'Load and plot Visium spots, Xenium cells and the whole-transcriptome Atera run.', '~35 min'],
    ['02 · Niche analysis', 'Find the niches of a tumour microenvironment from which cells sit next to which.', '~35 min'],
    ['03 · Cell–cell interaction', "LIANA+'s consensus ligand–receptor test on the same cells.", '~30 min'],
    ['04 · ViT for gene expression', 'Train a Vision Transformer that predicts expression from H&E alone.', '~40 min'],
  ], { x: 0.70, y: TOP + 0.10, w: 11.93, colW: [3.05, 7.28, 1.60], size: 15, rowH: 0.62 });

  s.addText([
    { text: 'Every Tutorial is self-contained and one click from the README:', options: { breakLine: true } },
    { text: 'github.com/xiao233333/ASI-FIMSA-workshop-2026', options: { bold: true } },
  ], {
    x: 0.70, y: 5.55, w: 11.93, h: 0.85,
    fontFace: FACE, fontSize: 17, color: BLACK, valign: 'top', margin: 0,
  });
  s.addNotes([
    'Set expectations on time. The numbers are wall-clock for a Participant reading as they go, not compute time --',
    'the headless suite runs all five in 348 s total.',
    '',
    'Self-contained matters: if someone loses their session in Tutorial 2, they can open Tutorial 3 and carry on.',
    'Nothing carries state between Tutorials.',
    '',
    'More is authored than fits. Say so now so nobody feels behind when we skip a section.',
  ].join('\n'));
}

// =============================================================================
// Starting Colab
// =============================================================================
{
  const s = slide('One click opens it; Runtime → Run all does the rest');
  const steps = [
    ['1', 'Click the badge', 'One per Tutorial in the README. Opens in your browser.'],
    ['2', 'Runtime → Run all', 'Then wait. There is nothing else to click.'],
    ['3', 'The install cell', 'About two minutes. It runs once per session.'],
    ['4', 'Read downwards', 'Every cell is explained in the text above it.'],
  ];
  // Number above the heading, not beside it: "Runtime -> Run all" wraps in a
  // 2.1in column and the second line lands on top of the detail text.
  cardRow(s, steps, { y: TOP + 0.05, h: 1.92, tagSize: 20, headY: 0.49, headH: 0.46, detailY: 0.99 });

  bullets(s, { x: 0.70, y: 3.48, w: 7.10, h: 2.70 }, [
    'You need a Google account. Colab is free and needs no card.',
    'Run 00 · Setup check at home. It downloads about 300 MB, which conference wifi may not enjoy.',
    'Nothing is saved to your Google Drive unless you ask for it.',
  ], 17);

  figure(s, 'nb00_blobs', { x: 8.20, y: 3.42, w: 4.20, h: 2.55 });
  s.addText('Setup check, Step 3b', {
    x: 8.20, y: 6.04, w: 4.20, h: 0.30,
    fontFace: FACE, fontSize: 12, color: GREY, align: 'center', valign: 'top', margin: 0,
  });
  s.addNotes([
    'Do this live on the projector once, slowly, before anyone opens their own laptop.',
    '',
    'The single most common failure in a room this size is people clicking individual cells out of order.',
    'Runtime -> Run all removes that entirely. Say it twice.',
    '',
    'Step 3b exists so a Participant sees something that is unmistakably working. If they get the three blobs,',
    'their session can install, import, reach the data and draw -- which is every prerequisite the Workshop has.',
  ].join('\n'));
}

// =============================================================================
// When Colab misbehaves
// =============================================================================
{
  const s = slide('If pip replaces a package, restart the session');
  s.addShape(pres.ShapeType.roundRect, {
    x: 0.70, y: TOP + 0.08, w: 11.93, h: 1.05,
    fill: { color: PANEL }, line: { color: PANEL }, rectRadius: 0.06,
  });
  s.addText([
    { text: 'PLEASE RESTART THE SESSION, THEN RUN THIS NOTEBOOK AGAIN FROM THE TOP.', options: { bold: true, breakLine: true } },
    { text: 'Use the menu:  Runtime → Restart session', options: {} },
  ], {
    x: 1.00, y: TOP + 0.20, w: 11.33, h: 0.85,
    fontFace: 'Courier New', fontSize: 17, color: BLACK, valign: 'top', margin: 0,
  });
  s.addText('Installing the stack upgrades pandas, and Colab has already imported it. Every install cell watches for this and prints the banner itself.', {
    x: 0.70, y: 2.52, w: 11.93, h: 0.42,
    fontFace: FACE, fontSize: 16, color: GREY, valign: 'top', margin: 0,
  });

  bullets(s, { x: 0.70, y: 3.12, w: 11.93, h: 3.20 }, [
    'A GPU is optional. Every Tutorial runs on the ordinary free CPU runtime; Tutorial 4 is a few minutes quicker with one. If you want it: Runtime → Change runtime type → T4 GPU.',
    'Sessions are disposable. Close the tab, open the Tutorial again, start over. Nothing on your own machine can be broken by anything here.',
    'Colab wipes what you install when a session ends, so you run an install cell at the start of each Tutorial. That is expected, not a mistake.',
    'On the day, Tutorial 4 pulls a further 1.8 GB full-resolution H&E from 10x over Google’s network, not the wifi in the room.',
  ], 17);
  s.addNotes([
    'This slide is insurance. Show it, do not dwell -- come back to it when a hand goes up.',
    '',
    'The restart is the one genuinely confusing moment: pip replaces pandas under a kernel that already imported it,',
    'so the session must restart before the new version is visible. Only three packages get replaced in total',
    '(pandas, tifffile, gdown); numpy and torch are deliberately left at Colab\'s own versions.',
    '',
    '"Nothing is broken" is the message that keeps a room calm. Repeat it whenever someone looks stuck.',
  ].join('\n'));
}

// =============================================================================
// Tutorial 1 — background
// =============================================================================
exhibit(
  'Tutorial 1: dissociation answers what is there, never where',
  'nb01_atera_wholeslide',
  [
    '170,057 cells, 13 annotated types, every one of them placed. Dissociate the same tissue and you keep the types and lose the positions.',
    'The myoepithelial rim around each duct is the histological signature of ductal carcinoma in situ. No UMAP can show it.',
    'The immune infiltration is heterogeneous across a single slide: dense in places, absent in others.',
  ],
  'Tutorial 1 §3.3  ·  Atera whole-transcriptome Xenium preview  ·  CC BY 4.0, 10x Genomics',
  [
    'This is the motivating slide for the whole Workshop. Give it time.',
    '',
    'The honest comparison: run this tissue through scRNA-seq and you would recover the same thirteen populations, in roughly',
    'the same proportions, with better per-cell depth. Everything you can see on this figure -- the rim, the ducts, the',
    'gradient of infiltration from one edge to the other -- is what dissociation costs.',
    '',
    'The Tutorial makes this concrete by drawing the same 170,057 points as a UMAP immediately after. Same cells, one arranged',
    'by where they were, the other by what they were expressing. Neither is wrong; they answer different questions.',
    '',
    'Say "Atera", not "Xenium v2". It is pre-release 10x chemistry on a Gen2 prototype.',
  ].join('\n'));

{
  const s = slide('Two families of technology: capture the tissue, or image it in place');
  table(s, [
    ['', 'Sequencing-based', 'Imaging-based'],
    ['How it works', 'mRNA is captured on a barcoded surface, then sequenced', 'probes bind transcripts and are imaged in place, cycle by cycle'],
    ['One measurement is', 'a fixed-size spot, and whatever cells fall in it', 'one cell, segmented from the image'],
    ['Which genes', 'the whole transcriptome, chosen by nobody', 'whatever is on the panel — until Atera'],
    ['Here', 'Visium', 'Xenium, Atera'],
  ], { x: 0.70, y: TOP + 0.10, w: 11.93, colW: [2.35, 4.79, 4.79], size: 15, rowH: 0.60 });

  // rowH is a minimum: LibreOffice grows a row to fit its longest cell, so the
  // bullets start well below the table's nominal bottom edge.
  bullets(s, { x: 0.70, y: 4.95, w: 11.93, h: 1.35 }, [
    'An imaging panel is designed before the experiment and fixes what is measurable.',
    'Atera is the first of the imaging family to drop that constraint.',
  ]);
  s.addNotes([
    'Two sentences of physics that explain every difference the Participants are about to see.',
    '',
    'Capture: the tissue sits on a slide printed with barcoded oligos, mRNA diffuses down onto them, and the barcode records',
    'which spot it came from. Resolution is the spot pitch, and the gene set is whatever sequencing returns -- so, everything.',
    '',
    'Imaging: nothing leaves the slide. Probes bind their targets and are read out optically over many cycles, so resolution is',
    'optical and the gene set is whatever probes were designed. Hence 313 genes on the Xenium panel.',
    '',
    'The trade is structural, not a vendor choice. Every "which platform should I use" question reduces to this table.',
  ].join('\n'));
}

{
  const s = slide('Everything lands in one SpatialData object, in one coordinate system');
  cardRow(s, [
    ['.images', 'Pixels', 'H&E and morphology stains, usually stored at several resolutions.'],
    ['.shapes', 'Geometry', 'Visium spots and cell boundaries, as circles or polygons.'],
    ['.points', 'Molecules', 'Individual transcripts, one row each, with coordinates.'],
    ['.tables', 'Counts', 'An AnnData of cells by genes, annotating one of the elements above.'],
  ], { y: TOP + 0.05, h: 2.02, tagSize: 18, headY: 0.52, headH: 0.40, detailY: 0.96 });

  bullets(s, { x: 0.70, y: 3.58, w: 11.93, h: 2.72 }, [
    'The elements do not share a pixel grid. Each carries a transformation into a named coordinate system, and that is what lines them up.',
    'Xenium ships its polygons in micrometres while its "global" system is in camera pixels. Mixing the two silently misplaces every cell.',
    'import spatialdata_plot looks unused. It registers the .pl accessor onto every object, which is how the figures get drawn.',
  ]);
  s.addNotes([
    'The Participants will type against this object for two hours, so name its parts once here rather than mid-Tutorial.',
    '',
    'The single idea worth landing: a SpatialData object is not one image with things drawn on it. It is several independent',
    'elements, each with its own native units, plus the transformations that put them in a shared frame. That is why you can',
    'crop an H&E and have the cell boundaries come with it.',
    '',
    'The unit surprise is real and Tutorial 1 walks into it deliberately in Section 2.5. It is also the same class of bug as the',
    'aligned-versus-raw Atera frame in the prep pipeline: two coordinate systems, no error message, every cell in the wrong place.',
    '',
    'If asked why spatialdata_plot is imported but never called: accessor registration is an import side effect. Nothing to fix.',
  ].join('\n'));
}

// =============================================================================
// Tutorial 1 — the platform trade-off
// =============================================================================
{
  const s = slide('Every platform trades genes against cells: read the table as a diagonal');
  table(s, [
    ['Platform', 'One measurement is', 'How many genes'],
    ['Visium', 'a 55 µm spot: a small disc of tissue holding several cells', 'whole transcriptome, ~36,600'],
    ['Xenium', 'one cell', 'a targeted panel, 313'],
    ['Atera', 'one cell', 'whole transcriptome, ~18,000'],
  ], { x: 0.70, y: TOP + 0.18, w: 11.93, colW: [2.20, 6.00, 3.73], size: 16, rowH: 0.58 });

  s.addText('Samples: V1_Breast_Cancer_Block_A_Section_1  ·  Xenium_FFPE_Human_Breast_Cancer_Rep1  ·  Atera WTA preview, Gen2 prototype', {
    x: 0.70, y: 3.86, w: 11.93, h: 0.30,
    fontFace: FACE, fontSize: 13, color: GREY, valign: 'top', margin: 0,
  });

  bullets(s, { x: 0.70, y: 4.35, w: 11.93, h: 1.95 }, [
    'Visium gives you every gene but not every cell. Xenium gives you every cell but only the genes someone chose in advance.',
    'Atera is the corner that used not to exist: single-cell resolution and the whole transcriptome, over 170,057 cells.',
    'Three different FFPE specimens of human breast carcinoma, not serial sections of one block. All three from 10x Genomics.',
  ]);
  s.addNotes([
    'This is the intellectual spine of the whole Workshop. Spend a minute on it.',
    '',
    'Draw the diagonal with your hand on the projector: top-left is genes, middle is cells, bottom is both.',
    'Everything the Participants see for the next two hours is a consequence of where a platform sits on that diagonal.',
    '',
    'Atera is 10x pre-release chemistry on a Gen2 prototype instrument. Call it Atera, not "Xenium v2" -- and note the',
    'full slide is far too large for a Colab session, so Tutorials 2 and 3 work on a prepared Crop.',
  ].join('\n'));
}

// =============================================================================
// Tutorial 1 — exhibits
// =============================================================================
exhibit(
  'A 55 µm spot shows architecture nobody annotated, and hides everything inside it',
  'nb01_visium_genes',
  [
    'EPCAM and ERBB2 light up the same territory; COL1A1 fills the space between them. That is the tumour and stroma architecture of the section, visible before anyone annotated anything.',
    'Now look at PTPRC. Low and diffuse almost everywhere.',
    'Every spot is a mixture of cells, and you cannot co-localise within one.',
  ],
  'Tutorial 1 §1.6  ·  Visium V1_Breast_Cancer_Block_A_Section_1, 3,798 spots under tissue  ·  data: 10x Genomics',
  [
    'Ask the room what they see before you say anything. Somebody always finds the anticorrelation unprompted,',
    'and it lands much harder that way.',
    '',
    'PTPRC is the immunology hook and the first limitation of the day: CD45 is real, present, and smeared across',
    'the whole section because a 55 um spot averages several cells. You cannot ask "is this T cell inside the duct"',
    'of this data at all. That question is what Tutorial 1 Section 2 is for.',
    '',
    'If asked about the missing H&E: this Tutorial deliberately skips the 1.8 GB full-resolution image. Tutorial 4 downloads it.',
  ].join('\n'));

exhibit(
  'Xenium resolves single cells, so you can ask whether the T cells are inside the duct',
  'nb01_xenium_boundaries',
  [
    '6,269 cells in one square millimetre, clustered and drawn as their real segmentation boundaries.',
    '313 genes, and 228 columns that are not genes: on-slide negative controls with no equivalent in a sequencing assay.',
    'Adjacency stops being a guess and becomes a question you can answer. That is Tutorial 2.',
  ],
  'Tutorial 1 §2.8  ·  Xenium_FFPE_Human_Breast_Cancer_Rep1  ·  Janesick et al., Nat Commun 14, 8353 (2023)',
  [
    'The teaching point here is the negative controls, not the clusters. An imaging assay can measure its own false-positive',
    'rate on the same slide, because a probe that targets nothing should detect nothing. Sequencing cannot do that.',
    '',
    'Point at a duct on the projector and ask the question out loud: are the T cells inside it or around it? Visium could',
    'not answer that. This can. Hold the answer over until Tutorial 2 -- it is the same question, made quantitative.',
    '',
    'The Tutorial builds a fake empty cells.zarr.zip so the reader works without the real 315 MB file. Mention only if asked.',
  ].join('\n'));

exhibit(
  'Atera gives both. But any one gene is sparse, and deconvolution is not resolution.',
  'nb01_triptych',
  [
    'The same 500 µm of tumour, three ways: 35 Visium spots, 1,776 Xenium cells, 1,138 Atera cells.',
    'Whole transcriptome at cell resolution is still sparse: EPCAM in ~47% of Atera cells, ERBB2 in ~4%.',
    'Xenium expands nuclei and tiles the plane; Atera leaves the extracellular space empty.',
  ],
  'Tutorial 1 §4.2  ·  Atera whole-transcriptome Xenium preview, 18,028 genes, 170,057 cells  ·  CC BY 4.0, 10x Genomics',
  [
    'The gaps in the right-hand panel are the slide to slow down on. They are not missing cells -- they are extracellular',
    'space that Atera\'s boundary-stain segmentation declines to claim, where Xenium\'s nucleus expansion tiles the plane',
    'regardless. Two defensible choices producing two different cell areas from the same tissue.',
    '',
    'Closing line of Tutorial 1: deconvolution is not resolution. You can estimate what mix of cell types is under a Visium',
    'spot, and that estimate is genuinely useful, but it will never tell you which cell was touching which.',
  ].join('\n'));

// =============================================================================
// Tutorial 2 — background
// =============================================================================
exhibit(
  'Tutorial 2: a cell-type list is a census, not an architecture',
  'nb02_demo_neighbourhood',
  [
    'Two tumour cells, same type, same expression. One is buried in tumour, the other sits at the immune interface.',
    'Nothing about the cells themselves separates them. Everything about their neighbourhoods does.',
    'Immune-excluded, inflamed and desert are claims about neighbourhoods. A table of cell-type counts cannot make them.',
  ],
  'Tutorial 2 §2.1  ·  900 synthetic cells, 10 nearest neighbours',
  [
    'Nine hundred fake cells, because the idea should land before any real data complicates it.',
    '',
    'Point at cell A, then cell B. Both are red. Both would be one row of "Tumour epithelial" in any cell-type table, and in a',
    'differential-expression test they would be pooled. Yet one of them is in a place where a T cell could reach it and the',
    'other is not, and if you care about immunotherapy that difference is the entire question.',
    '',
    'The construction of the rest of the Tutorial follows directly: describe each cell by the mix of types around it, and',
    'suddenly A and B are different objects. That vector is all the niche methods need.',
    '',
    'Ask which of the three clinical phenotypes this synthetic tissue is. It is immune-excluded -- the ring is on the outside.',
  ].join('\n'));

exhibit(
  'Coordinates become a graph before they become a statistic',
  'nb02_delaunay',
  [
    'Delaunay triangulation, a fixed radius, or k nearest neighbours. Each defines "neighbour" differently, and none is the right one.',
    '3,843 edges in this 500 µm window. About 95% are shorter than 36 µm; the longest runs roughly 1,700 µm across a gap in the tissue.',
    'Look at the graph before you trust anything computed on it.',
  ],
  'Tutorial 2 §3.1  ·  sq.gr.spatial_neighbors(delaunay=True)',
  [
    'Every method in this Tutorial and the next one is a statistic over a graph, and the graph is a choice nobody shows you.',
    '',
    'Delaunay has one appealing property: it never leaves a cell isolated and it adapts to local density. It has one bad one,',
    'visible here -- it will happily connect two cells across an empty lumen, because triangulation has no notion of tissue.',
    'A fixed radius has the opposite failure: in sparse stroma a cell can end up with no neighbours at all.',
    '',
    'The 1,700 um edge is the honest version of that. It is a real edge in this graph, it is not a bug, and it is the reason',
    'the Tutorial plots the edge-length distribution rather than trusting the defaults.',
    '',
    'If someone asks which to use: whichever you can defend, and report it. The answers do move.',
  ].join('\n'));

{
  const s = slide('Three routes from a graph to a niche, answering three different questions');
  table(s, [
    ['Route', 'What it computes', 'What comes back'],
    ['squidpy\nnhood_enrichment', 'how often each pair of cell types is adjacent, against shuffled labels', 'one z-score per pair of types, for the whole Crop'],
    ['kNN composition\n+ KMeans', 'the mix of cell types around every cell, then clusters those profiles', 'a niche label for every single cell'],
    ['sopa\nvectorize_niches', 'those labels turned into geometry', 'area, roundness, components, and distance in hops'],
  ], { x: 0.70, y: TOP + 0.14, w: 11.93, colW: [2.95, 5.10, 3.88], size: 15, rowH: 0.70 });

  bullets(s, { x: 0.70, y: 5.05, w: 11.93, h: 1.25 }, [
    'The first returns one number for the whole tissue. That is why the other two exist.',
    'All three take a scale parameter, and the answer changes with it. Report the number you used.',
  ]);
  s.addNotes([
    'A map of Sections 3, 4 and 5, so nobody wonders halfway through why we are doing the same thing three times.',
    '',
    'They are not the same thing. Route one is a hypothesis test about types. Route two is an unsupervised description of',
    'places. Route three turns places into objects with measurable geometry. Each is strictly more specific than the last,',
    'and each costs another assumption.',
    '',
    'The scale parameter is the transferable lesson: k = 20 neighbours in route two, a 50 um radius in route three, and the',
    'triangulation itself in route one. Change any of them and the niches change identity, not just their boundaries.',
    '',
    'Section 4.5 demonstrates that directly at k = 5, 20 and 50. Show it if there is time.',
  ].join('\n'));
}

// =============================================================================
// Tutorial 2 — exhibits
// =============================================================================
exhibit(
  'A cell-type list says who is in the room, not who is standing with whom',
  'nb02_crop_overview',
  [
    'The Crop: a 2,000 µm square, 16,006 cells, 12 named types. 43% is tumour epithelium.',
    '400 cells stay Unassigned and are kept. Dropping them would quietly delete the cells the method understood least.',
    'Three questions follow: which types sit together, what niches exist, and how far apart they are.',
  ],
  'Tutorial 2 §1.2  ·  Atera Crop, one 18 MB download  ·  cell types from a human-reviewed annotation of 34 vendor clusters',
  [
    'Why a Crop and not the whole slide: 170,057 cells with imagery will not load in a Colab session. This window was',
    'chosen for mixture rather than density -- entropy 0.76 against 0.54 for the densest candidate, which was solid tumour',
    'and would have taught nothing about who stands next to whom.',
    '',
    'The Unassigned point is worth thirty seconds. It is a habit, not a detail: the cells a classifier is least sure about',
    'are exactly the ones people delete, and deleting them makes every downstream figure look cleaner than the data is.',
  ].join('\n'));

exhibit(
  'Tumour epithelium avoids T cells at z ≈ −72: an immune-excluded tumour',
  'nb02_nhood_enrichment',
  [
    'squidpy builds a Delaunay graph, then shuffles the labels 200 times to ask which pairs are adjacent more often than chance.',
    'Tumour self-enrichment is z ≈ +119. Against T cells −72, dendritic cells −43, macrophages −34.',
    'The lymphocytes are present, in decent numbers, and they are not getting in.',
    'Endothelial ↔ perivascular at +41 is the positive control: two types that must be adjacent, and are.',
  ],
  'Tutorial 2 §3  ·  sq.gr.spatial_neighbors(delaunay=True) + sq.gr.nhood_enrichment, 200 permutations',
  [
    'This is the immunology slide of Tutorial 2. Everything before it is setup.',
    '',
    'Always show them the positive control. Endothelial and perivascular cells are adjacent by construction, so if that',
    'pair had not come out warm the method would be broken. A reader who checks their own positive control is doing',
    'the analysis; one who reports only the exciting number is doing something else.',
    '',
    'Limitation to name before they do: this gives one number per pair of types for the entire Crop. It cannot tell you',
    'that the immune cells are excluded HERE and infiltrating THERE. That is what the niches in Section 4 are for.',
  ].join('\n'));

exhibit(
  'Niches built with no knowledge of position come out spatially coherent',
  'nb02_niches_on_tissue',
  [
    'Neighbourhood composition from the 20 nearest cells (about 60 µm), then KMeans into 8 niches.',
    'The clustering never saw a coordinate, only the mix of types around each cell. The coherence was in the tissue.',
    'k is the spatial-scale knob. A niche is a property of a tissue at a stated scale.',
  ],
  'Tutorial 2 §4.3  ·  kNN composition + MiniBatchKMeans  ·  adapted from gml-teaching-2026, 3.2_neighborhood.ipynb',
  [
    'Left panel is the input, right panel is the output. Make the room compare them: the niches are not just recoloured',
    'cell types -- "Tumour boundary" and "Proliferating tumour front" are new objects that no single cell carries a label for.',
    '',
    'The coherence argument is the one to make carefully. KMeans was given a composition vector per cell and nothing else.',
    'If the labels come back in spatially contiguous blobs, that structure was in the tissue, not in the method.',
    '',
    'The Tutorial re-runs this at k = 5, 20 and 50. If there is time, show that figure: the niches genuinely change identity.',
  ].join('\n'));

exhibit(
  'Tumour interiors sit 15 or more cell-to-cell steps from the nearest immune cell',
  'nb02_hops_to_immune',
  [
    'sopa turns each niche into a polygon you can measure: area, roundness, and distance in graph hops.',
    'Median hops to the immune infiltrate niche: tumour epithelial 9, proliferating tumour 7, T cells 0.',
    'Dendritic cells sit closer to the tumour niches than T cells do. This is "immune-excluded" as a number.',
  ],
  'Tutorial 2 §5.4  ·  sopa.spatial.vectorize_niches / cells_to_groups / mean_distance',
  [
    'The black cells in the left panel are the punchline: the interiors of the largest tumour masses are 15+ steps from any',
    'immune cell. The immune compartment presses against the tumour everywhere and penetrates it almost nowhere.',
    '',
    'The dendritic-cell result usually gets a reaction. Do not over-read it -- one Crop, one specimen -- but it is exactly the',
    'kind of hypothesis this analysis exists to generate.',
    '',
    'Caution to state: compare niches within one buffer setting, never a niche from one analysis against a niche from another.',
    'Roundness around 0.3-0.4 here means interdigitating, infiltrative margins rather than compact nodules.',
  ].join('\n'));

// =============================================================================
// Tutorial 3 — background
// =============================================================================
{
  const s = slide('Tutorial 3: adjacency is not conversation');
  cardRow(s, [
    ['What is measured', 'Two mRNAs and a distance',
     'Ligand mRNA in one population, receptor mRNA in another, and how far apart the cells sit.'],
    ['What is claimed', 'A signalling axis',
     'That these two populations are communicating through this pair, somewhere in this tissue.'],
    ['What is never measured', 'Everything in between',
     'Protein, secretion, contact, receptor engagement, or anything downstream of it.'],
  ], { y: TOP + 0.10, h: 2.62, tagSize: 16, headSize: 17, headY: 0.60, headH: 0.52, detailY: 1.24, gap: 0.28 });

  s.addText('The gap is not a flaw to apologise for. It is what makes this a hypothesis generator with coordinates, rather than a result.', {
    x: 0.70, y: 4.40, w: 11.93, h: 0.90,
    fontFace: FACE, fontSize: 19, color: BLACK, valign: 'top', margin: 0,
  });
  s.addNotes([
    'Tutorial 2 established who stands next to whom. This one asks what they are saying, and the honest answer is that we',
    'are inferring it from two transcripts and a distance.',
    '',
    'Set the expectation here rather than in the limitations section at the end. An immunologist knows perfectly well that',
    'CXCL12 mRNA in a fibroblast does not mean CXCL12 protein reached a T cell. Saying it first buys credibility for',
    'everything that follows; saying it last sounds like a hedge.',
    '',
    'The framing that works: this is the same epistemic status as a differential-expression hit. Nobody thinks a volcano plot',
    'proves a mechanism, but everybody uses one to decide what to do next. Ligand-receptor inference is that, with coordinates.',
  ].join('\n'));
}

{
  const s = slide('LIANA+ is a consensus of five scores over a database somebody curated');
  table(s, [
    ['Score', 'What it rewards'],
    ['CellPhoneDB', 'a pair expressed in a high fraction of both populations, tested against permuted labels'],
    ['Connectome', 'a pair whose ligand and receptor are both high relative to the other populations'],
    ['log2FC', 'a pair enriched in this sender and this receiver against everything else'],
    ['NATMI', 'specificity: a pair carried by these two populations and few others'],
    ['SingleCellSignalR', 'magnitude: the LRscore, a bounded product of the two expression levels'],
  ], { x: 0.70, y: TOP + 0.06, w: 11.93, colW: [3.10, 8.83], size: 15, rowH: 0.52 });

  bullets(s, { x: 0.70, y: 4.62, w: 11.93, h: 1.68 }, [
    'RobustRankAggregate combines the five into magnitude_rank and specificity_rank. Smaller is stronger, and smaller is more specific.',
    'Complexes are encoded, so LFA-1 is ITGAL_ITGB2 and every subunit must be measured. A pair absent from the database is not refuted; it is never asked.',
  ]);
  s.addNotes([
    'The reason to teach LIANA+ rather than any single tool: you get to see that the choice of scoring function is itself a',
    'variable, instead of inheriting somebody else\'s.',
    '',
    'Notice the two axes in the right-hand column. Some of these reward magnitude -- a lot of signal -- and some reward',
    'specificity -- signal that these two populations have and others do not. They disagree, routinely, and the aggregate',
    'reports both ranks separately for exactly that reason.',
    '',
    'The complex point matters clinically. If your panel has ITGAL but not ITGB2, LFA-1 is unevaluable, and no amount of',
    'ITGAL signal will produce it. That is the previous slide\'s panel argument arriving in code.',
    '',
    'Do not claim these are five independent experiments. Five statistics over one matrix share every bias that matrix has.',
  ].join('\n'));
}

exhibit(
  'Space enters as a kernel over distance, and you choose the scale',
  'nb03_proximity',
  [
    'A Gaussian kernel weights every pair by how far apart the cells are, with a cutoff below which the pair stops counting.',
    'Two questions, two bandwidths: 15 µm for per-cell local scores, 30 µm for between-population proximity.',
    'This matrix is the population-scale object: how close, on average, each sender sits to each receiver.',
  ],
  'Tutorial 3 §4.1  ·  li.ut.spatial_pair_proximity, 30 µm bandwidth  ·  directed: sender rows, receiver columns',
  [
    'The matrix is worth reading aloud for thirty seconds, because it previews the answer. Tumour epithelial to T cell is 0.00.',
    'T cell to fibroblast is 0.82. The exclusion is already visible in the geometry, before any ligand-receptor score is computed.',
    '',
    'It is directed, and asymmetric for a real reason: it is a mean over sender cells of the weighted distance to receiver cells,',
    'so a rare population near a common one scores differently from the reverse.',
    '',
    'Two bandwidths, two scales, and this is the single easiest thing to get wrong in the Tutorial. A per-cell graph wants a',
    'few cell diameters. Between-population mean distances on this Crop span 9 to 224 um, so at 15 um the weighting annihilates',
    'nearly every cross-population score. Hence 30 um here and 15 um in Section 6. Two numbers, two jobs.',
  ].join('\n'));

// =============================================================================
// Tutorial 3 — exhibits
// =============================================================================
exhibit(
  'The gene panel decides which questions you are allowed to ask',
  'nb03_panel_support',
  [
    'Two databases, the same 16,006 cells. The 1,673-gene panel supports 3,738 testable interactions; the 69-gene panel supports four.',
    'An interaction counts only if every subunit is measured. LFA-1 is ITGAL_ITGB2, not ITGAL.',
    'Intersect the analysis you intend to run with the probe list before you buy the panel.',
  ],
  'Tutorial 3 §1.2  ·  LIANA+ consensus resource and connectomeDB2020',
  [
    'Open Tutorial 3 on this slide, not on a result. It is the most transferable thing in the whole Workshop and it costs',
    'nothing to act on.',
    '',
    'The four-versus-3,738 gap is not a criticism of the 69-gene panel -- that panel was designed to name cell types and it',
    'does that well. It is a demonstration that panel design silently fixes which questions are answerable, months before',
    'anyone opens a notebook.',
    '',
    'Related trap: CSF1_CSF1R and B2M_HLA-F are not in this resource at all. A pair absent from your database is not',
    'refuted -- it is never asked.',
  ].join('\n'));

exhibit(
  'The top of a ranked ligand–receptor list follows abundance, not importance',
  'nb03_top_pairs',
  [
    'LIANA+ is a consensus, not a method: five scores rank-aggregated into a single ordering.',
    'GNAS is detected in 74% of cells, ARF1 in 57%, CDH1 in 53%. The ranking reports opportunity.',
    'Five statistics computed over one matrix are not five independent experiments.',
  ],
  'Tutorial 3 §3.1  ·  li.mt.rank_aggregate, expr_prop 0.05, min_cells 20, 100 permutations',
  [
    'Read the top of the left-hand panel out loud -- GNAS to ADCY1, collagens to integrins -- and ask whether anyone would',
    'write a paper about it. That reaction is the lesson.',
    '',
    'The consensus is a real strength: no single scoring function gets to decide. But be honest about what it is not.',
    'Five functions over the same expression matrix share every bias that matrix has, abundance most of all.',
    '',
    'Methods note if asked: 100 permutations cannot resolve a p-value below 0.01. For publication use 1,000 or more.',
    'We use 100 so the cell finishes in twenty seconds in a teaching session.',
  ].join('\n'));

exhibit(
  'Spatial weighting re-orders almost everything. It is a constraint, not an accuracy.',
  'nb03_spatial_ab',
  [
    'The same consensus run twice, expression only then spatially weighted: 53.7% promoted, 46.3% demoted.',
    'Spatial weighting is not a filter. It asks a different question, and nearly every pair moves.',
    'Bandwidth is not a radius: the furthest cell above cutoff sits at 2.15 × bandwidth.',
  ],
  'Tutorial 3 §5.1  ·  30,469 unsaturated cross-population rows; saturated magnitude_rank = 1.0 excluded first',
  [
    'The bandwidth arithmetic is the single most useful thing on this slide. People set bandwidth to the distance they',
    'mean and quietly analyse a neighbourhood twice the size they intended. A 30 um hard radius gives a median of 14',
    'neighbours here; a 30 um LIANA bandwidth gives 60.',
    '',
    'Mention the ceiling trap only if someone asks why n is 30,469: about a fifth of cross-population rows sit at the',
    'saturation value magnitude_rank = 1.0, and comparing ranks without excluding them manufactures movement that is not there.',
    '',
    'The honest summary: adding space does not make the answer more correct, it makes it a different answer under a',
    'different assumption. Say which assumption you made.',
  ].join('\n'));

exhibit(
  'CXCL12–CXCR4 paints the same immune-exclusion geometry Tutorial 2 drew',
  'nb03_local_cxcl12',
  [
    'Per-cell local scores, not one number per population. The signal fills the stroma between the epithelial blocks and avoids the tumour nests.',
    'T cell ↔ dendritic cell dominates the immune half of this tumour. ICAM1–ITGAL/ITGB2 is the adhesion step of the immunological synapse.',
    'CD274–PDCD1 is filtered out entirely. That is a statement about detection, not about the tumour.',
  ],
  'Tutorial 3 §6.1  ·  li.mt.bivariate, bandwidth 15 µm, Moran’s R  ·  LIANA+: Dimitrov et al., Nat Cell Biol 26, 1613 (2024)',
  [
    'This is the convergence slide. Tutorial 2 found immune exclusion from adjacency alone; Tutorial 3 finds the same',
    'geometry from a completely different statistic on a different gene set. Neither one knew about the other.',
    '',
    'Guard against over-reading: Moran\'s R is not a significance test for signalling. It says the local scores are spatially',
    'structured, which is a much weaker claim than "these cells are talking".',
    '',
    'The PD-L1/PD-1 absence is worth naming plainly. It is the pair an immunologist would ask for first, and it is not here',
    'because the transcripts are too sparse to survive the expression filter -- not because the axis is inactive.',
    '',
    'And: only 91 plasma cells in this Crop against 1,590 T cells. A missing cell type is a harder limit than a missing gene.',
  ].join('\n'));

// =============================================================================
// Tutorial 4 — background
// =============================================================================
exhibit(
  'Tutorial 4: can a model read biology off morphology, gene by gene?',
  'nb04_spots_on_image',
  [
    'Every Visium spot carries two things: a patch of H&E and a vector of gene counts. The question is whether the first predicts the second.',
    'A pathologist already does a version of this by eye. This asks for it quantitatively, one gene at a time.',
    'The lineage: ST-Net and HE2RNA in 2020, then HisToGene. Production methods now start from a pathology foundation model.',
  ],
  'Tutorial 4 §1.2  ·  Visium V1_Breast_Cancer_Block_A_Section_1, 3,798 spots under tissue',
  [
    'The premise is not exotic. Reading molecular state off morphology is what histopathology has always been; the claim here',
    'is only that it can be made numerical and checked.',
    '',
    'Why this matters practically: H&E is cheap, universal, and already sitting in every archive. If expression were readable',
    'from it, decades of stored blocks would become a spatial dataset. That is the promise, and Tutorial 4 tests it honestly',
    'rather than selling it.',
    '',
    'The paired structure on the right-hand panel is the whole setup. 3,798 spots, 3,798 image patches, 3,798 expression',
    'vectors, and a supervised regression between them.',
    '',
    'If someone asks why not use a foundation model: because then you learn nothing about what the model does. We build the',
    'smallest thing that works, and the last slide of the Tutorial names the production alternatives.',
  ].join('\n'));

{
  const s = slide('A Transformer is tokens, attention, and one token that reads the whole set');
  cardRow(s, [
    ['A token', 'One thing, as a vector', 'A word in a sentence, or here a small patch of the image.'],
    ['Self-attention', 'Everything asks everything', 'Every token queries every other and mixes in whatever it finds relevant.'],
    ['Position', 'Added, not assumed', 'Attention is blind to order, so where a token came from has to be told to it.'],
    ['[CLS]', 'The one that summarises', 'A token belonging to no patch, which ends up carrying the answer for all of them.'],
    // headH fits two lines: "Everything asks everything" does not fit one 2.4in line
    // at 16pt, and a heading that wraps must not land on the detail beneath it.
  ], { y: TOP + 0.05, h: 2.36, tagSize: 18, headY: 0.50, headH: 0.56, detailY: 1.12 });

  bullets(s, { x: 0.70, y: 3.92, w: 11.93, h: 2.38 }, [
    'A block is attention, then a small MLP, each with a bypass around it so the signal can skip past. Stack three and that is the model.',
    'Nothing in that description is specific to images. Swap patches for words and it is a language model.',
    'You build it from nn.MultiheadAttention and nn.LayerNorm in about forty readable lines, not from a library call.',
  ]);
  s.addNotes([
    'Most of the room has heard "Transformer" for three years without ever being told what one is. Fix that here, plainly,',
    'and the architecture slide later needs no explanation at all.',
    '',
    'The attention idea in one sentence: each token produces a query, every token produces a key, and the match between them',
    'decides how much of each other token gets mixed in. Nothing more mystical than a weighted average with learned weights.',
    '',
    'The [CLS] token is the part worth dwelling on because it is genuinely odd. You add a token that corresponds to nothing in',
    'the input, let it attend to everything for three layers, and then read your answer off it. It works because attention',
    'gives it no reason not to gather.',
    '',
    'The Tutorial demonstrates this on five random tokens in about thirty seconds of compute, and prints the 5x5 attention',
    'matrix. That demo converts more people than any diagram.',
  ].join('\n'));
}

exhibit(
  'A gene you cannot detect is a gene you cannot predict',
  'nb04_marker_sparsity',
  [
    'KRT8 and COL1A1 are measured almost everywhere. PTPRC and CD3D are patchy, and mostly zero.',
    'Sixteen targets: twelve hand-picked breast and immune markers, topped up by dispersion, each z-scored per gene.',
    'The metric is one Pearson r per gene on held-out spots, not one number for the model.',
  ],
  'Tutorial 4 §3.1  ·  measured expression in tissue space, log-normalised',
  [
    'This slide is here so the result three slides later is not a surprise. Half the answer is already visible: you cannot',
    'learn a mapping onto a column that is mostly zeros, and two of these four columns are mostly zeros.',
    '',
    'Contrast the panels deliberately. KRT8 and COL1A1 are smooth fields -- a model can learn a smooth field. PTPRC and CD3D',
    'are speckle, and speckle at this spot size is close to noise even before the image gets involved.',
    '',
    'Per-gene evaluation is the methodological point. A single mean r across sixteen genes would report 0.31 and sound fine.',
    'Splitting it by gene is what turns a mediocre aggregate into a usable statement about which biology is readable.',
    '',
    'Z-scoring per gene matters too: without it the loss would be dominated by whichever gene has the largest dynamic range,',
    'and the model would quietly optimise for KRT8 alone.',
  ].join('\n'));

// =============================================================================
// Tutorial 4 — exhibits
// =============================================================================
exhibit(
  'One H&E tile per spot, and full resolution is why a nucleus is 26 px and not 2',
  'nb04_tiles',
  [
    '3,798 Visium spots, one 390 px tile each, cut from the 1.8 GB full-resolution H&E and resized to 64 px.',
    'On the 2,000 px thumbnail an 8 µm nucleus is 2 pixels. At full resolution it is 26.',
    'Cut the tiles in adata.obs_names order. Any other order silently trains the model to r ≈ 0.',
  ],
  'Tutorial 4 §2  ·  Visium V1_Breast_Cancer_Block_A_Section_1, full-resolution H&E memory-mapped with tifffile',
  [
    'Hold a tile up against the room\'s intuition: a pathologist looks at exactly this and calls tumour, stroma or lymphocyte.',
    'The question of the Tutorial is whether a model can do it quantitatively, gene by gene.',
    '',
    'The resolution argument is measurable, not aesthetic: across four configurations and three seeds, full-resolution tiles',
    'give 0.3198 +/- 0.0060 against 0.3003 +/- 0.0233 from the thumbnail. Better mean, and four times less seed spread.',
    '',
    'The obs_names warning is the failure I would most like them to remember. It is silent. Nothing errors, no figure looks',
    'wrong, and the model simply learns nothing because every tile is matched to the wrong spot\'s expression.',
  ].join('\n'));

exhibit(
  'A 118,160-parameter ViT trains in three to six minutes on a free CPU runtime',
  'nb04_training',
  [
    'Plain PyTorch: an 8×8 patch embedding giving 64 tokens plus a [CLS], three blocks, four heads, d_model 64.',
    '2,848 training and 950 held-out spots, 16 marker genes z-scored, 35 epochs.',
    'Spots are split at random, so a validation spot often neighbours a training spot.',
  ],
  'Tutorial 4 §6  ·  derived from gml-teaching-2026, Deep_learning_04_vit_HE_spatial.ipynb',
  [
    'The point of building it by hand is not the performance -- it is that afterwards they know exactly what UNI, CONCH,',
    'Prov-GigaPath and Virchow are doing inside. Those are the same components at a hundred times the scale.',
    '',
    'Be candid about the random split. It leaks: neighbouring Visium spots share tissue, so the held-out r is optimistic.',
    'We keep it because a spatial split costs a slide of explanation, and the conclusion of the Tutorial -- the ranking of',
    'which genes are predictable -- survives it.',
    '',
    'CPU and GPU runs differ slightly. Floating-point addition is not associative. Look for stable conclusions, not identical numbers.',
  ].join('\n'));

exhibit(
  'Mean r ≈ 0.31: stromal genes predict from morphology, immune markers do not',
  'nb04_per_gene_r',
  [
    'DCN 0.47, KRT8 0.46, COL1A1 0.42. Then PTPRC 0.29, CD68 0.27, CD3D 0.23, MS4A1 0.17.',
    'Three reasons stacked: dropout, resolution, and morphological ambiguity.',
    'A small round blue cell on H&E could be a T cell, a B cell, an NK cell or a plasmacytoid dendritic cell. The information is not in the image, and no amount of training data fixes that.',
  ],
  'Tutorial 4 §7  ·  Pearson r on held-out spots, one CPU run; values move slightly between runs and between CPU and GPU',
  [
    'Red bars are the immune markers, and they are picked out in the figure for a reason: this is the immunology punchline',
    'of the entire Workshop.',
    '',
    'Take the three reasons in order. Dropout -- you cannot learn a mapping onto a column that is mostly zeros. Resolution --',
    'three T cells among seven tumour cells give a spot that is transcriptionally mostly tumour. Ambiguity -- even a perfect',
    'image does not distinguish the lymphocyte subsets, because the distinguishing information is not optical.',
    '',
    'Only the third is a hard limit. The first two get better with deeper sequencing and smaller spots; the third does not.',
  ].join('\n'));

exhibit(
  'It works best where you needed it least and worst where you needed it most',
  'nb04_predicted_on_tissue',
  [
    'DCN at r = 0.46: the model reproduces the stromal architecture of the section from morphology alone.',
    'IGLC7 at r = 0.08: the prediction collapses to a flat band at the mean. That is what “the information is not in the image” looks like.',
    'Predicting expression from H&E is real and useful. Any paper claiming to read the immune microenvironment off H&E deserves this chart pointed at it.',

  ],
  'Tutorial 4 §7.2  ·  measured against ViT-predicted, held-out spots, one shared colour scale',
  [
    'Compare the two right-hand panels, not the left-hand ones. Top right has structure; bottom right is uniform pink.',
    'The model has given up and is predicting roughly the mean for every spot, which is the rational thing to do when the',
    'input carries no information about the target.',
    '',
    'This is the slide to end the Tutorial on. It is not a negative result -- knowing the shape of the failure is what makes',
    'the method usable. Structural compartments: yes. Immune infiltration: no, and predictably no.',
  ].join('\n'));

// =============================================================================
// Conclusion
// =============================================================================
{
  const s = slide('Three methods, three failure modes, one consistent blind spot');
  const cards = [
    ['Tutorial 2', 'No B-cell cluster.', 'About 10% of cells carry at least one B-cell gene, but graphclust does not resolve them as their own population. No label was forced.'],
    ['Tutorial 3', 'Every immune pair ranks below the abundant adhesion biology.', 'CD274–PDCD1 cannot be evaluated at all: too sparse to survive the expression filter.'],
    ['Tutorial 4', 'The four immune markers are the worst four genes.', 'Stromal and epithelial genes predict from morphology. PTPRC, CD68, CD3D and MS4A1 do not.'],
  ];
  cardRow(s, cards, { y: TOP + 0.10, h: 3.30, tagSize: 16, headSize: 17,
                      headY: 0.60, headH: 1.10, detailY: 1.78, gap: 0.28 });
  s.addText('Every one of these methods has a boundary, and the boundary usually lands on the immune compartment. Knowing where it lands is the difference between using these tools and being used by them.', {
    x: 0.70, y: 5.10, w: 11.93, h: 1.10,
    fontFace: FACE, fontSize: 19, color: BLACK, valign: 'top', margin: 0,
  });
  s.addNotes([
    'End here. Do not add an outlook slide.',
    '',
    'The three failures were not arranged -- they fell out of three unrelated analyses on three different gene sets, and',
    'they land in the same place because immune cells are sparse, small, and morphologically ambiguous. That is a property',
    'of the biology and the measurement, not of any one tool.',
    '',
    'The Workshop is not arguing that spatial omics cannot do immunology. It is arguing that the failure modes are',
    'knowable in advance, and that a Participant who can predict where a method will break can design around it.',
  ].join('\n'));
}

// =============================================================================
// Credits and references
// =============================================================================
{
  const s = slide('Credits, licences and further reading');
  const rows = [
    ['Data', 'All three datasets are generated and released by 10x Genomics. Xenium breast: Janesick, Shelansky, Gottscho et al., Nat Commun 14, 8353 (2023). The Atera whole-transcriptome preview is CC BY 4.0; Visium and Xenium are downloaded from 10x directly and not redistributed here.'],
    ['Methods', 'LIANA+ — Dimitrov et al., Nat Cell Biol 26, 1613 (2024). squidpy, sopa, scanpy and the spatialdata family. Vision Transformer — Dosovitskiy et al., arXiv:2010.11929. Attention rollout — Abnar & Zuidema, arXiv:2005.00928.'],
    ['Material', 'Derived from the gml-teaching-2026 course of the Genomics and Machine Learning Lab, QIMR Berghofer Medical Research Institute | The University of Queensland. Teaching material and code are MIT licensed.'],
  ];
  let y = TOP + 0.15;
  rows.forEach(([label, body]) => {
    s.addText(label, {
      x: 0.70, y, w: 1.75, h: 0.4,
      fontFace: FACE, fontSize: 18, bold: true, color: RED, valign: 'top', margin: 0,
    });
    s.addText(body, {
      x: 2.55, y, w: 10.08, h: 1.45,
      fontFace: FACE, fontSize: 16, color: BLACK, valign: 'top', margin: 0,
    });
    y += 1.62;
  });
  s.addText('github.com/xiao233333/ASI-FIMSA-workshop-2026', {
    x: 0.70, y: 6.12, w: 11.93, h: 0.4,
    fontFace: FACE, fontSize: 18, bold: true, color: BLACK, valign: 'top', margin: 0,
  });
  s.addNotes([
    'Leave this up during questions.',
    '',
    'Thank 10x Genomics out loud. None of this Workshop exists without their public data, and the Atera preview in',
    'particular is pre-release chemistry they did not have to release at all.',
    '',
    'The repo is public and MIT licensed. Anyone can teach from it, and the notebooks contain far more prose than we',
    'reached today -- point people there rather than trying to answer everything in the room.',
  ].join('\n'));
}

pres.writeFile({ fileName: OUT }).then(() => {
  const kb = fs.statSync(OUT).size / 1024;
  console.log(`wrote ${OUT}  (${(kb / 1024).toFixed(1)} MB)`);
});
