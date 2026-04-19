#!/usr/bin/env node
/**
 * HUNTER — Export Hunt Plan to Word Document  v4
 * Usage: node export_docx.js <plan_json_path> <output_docx_path>
 * Requires: npm install docx  (run once in the project folder)
 *
 * v4 fixes:
 *   - Table border suppression uses w:val="nil" not "none" (Word strict mode fix)
 *   - Page number uses proper fldChar/instrText sequence not deprecated w:pgNum
 *   - Removed table-level tblBorders that conflict with cell-level borders
 */

// ── Resolve docx from THIS script's local node_modules first ─────────────────
const path   = require('path');
const Module = require('module');
const SCRIPT_DIR = path.dirname(path.resolve(__filename));
Module.globalPaths.unshift(path.join(SCRIPT_DIR, 'node_modules'));

const {
  Document, Packer, Paragraph, TextRun,
  Table, TableRow, TableCell,
  Header, Footer,
  HeadingLevel, AlignmentType, BorderStyle,
  WidthType, ShadingType, VerticalAlign,
  LevelFormat, PageBreak,
  // Field-based page number (replaces deprecated w:pgNum)
  SimpleField,
} = require('docx');

const fs = require('fs');

// ── Args ─────────────────────────────────────────────────────────────────────
const planPath = process.argv[2];
const outPath  = process.argv[3] || 'hunt_plan.docx';
if (!planPath) {
  console.error('Usage: node export_docx.js <plan.json> [output.docx]');
  process.exit(1);
}
const plan = JSON.parse(fs.readFileSync(planPath, 'utf8'));

// ── Palette ───────────────────────────────────────────────────────────────────
const C = {
  navy:    '0A2744',
  accent:  '0077A8',
  red:     'C1121F',
  white:   'FFFFFF',
  muted:   '6B7280',
  border:  'D1D5DB',
  rowHdr:  '0A3D5F',
  rowAlt:  'EBF8FD',
  mitre:   '4B2D8F',
  apt:     '7A1A1A',
  success: '1E6B45',
  amber:   'B45309',
};

const PRIO_COLORS = {
  Critical: 'C1121F',
  High:     'E76F51',
  Medium:   'F4A261',
  Low:      '3DD68C',
};

// ── Border helpers ────────────────────────────────────────────────────────────
// CRITICAL: Use BorderStyle.NIL (w:val="nil") to suppress borders — NOT "none"
// "none" is rejected by Word's strict XML validator; "nil" is correct OOXML.
const B_SINGLE = (color = C.border, size = 4) => ({
  style: BorderStyle.SINGLE, size, color,
});
const B_NIL = () => ({
  style: BorderStyle.NIL, size: 0, color: C.white,
});

// Cell border sets
const BORDERS_ALL = (color = C.border, size = 4) => ({
  top: B_SINGLE(color, size),
  bottom: B_SINGLE(color, size),
  left: B_SINGLE(color, size),
  right: B_SINGLE(color, size),
});

// For "invisible" table borders: nil on all sides
const BORDERS_NIL = () => ({
  top:     B_NIL(),
  bottom:  B_NIL(),
  left:    B_NIL(),
  right:   B_NIL(),
});

// Cell margins
const CM = { top: 80, bottom: 80, left: 120, right: 120 };
const CM_SM = { top: 60, bottom: 60, left: 100, right: 100 };

// ── Text run helper ───────────────────────────────────────────────────────────
function run(text, opts = {}) {
  return new TextRun({
    text: String(text ?? ''),
    font: opts.font || 'Arial',
    size: opts.size || 20,
    bold: opts.bold || false,
    color: opts.color || '111111',
    italics: opts.italic || false,
  });
}

// ── Paragraph helper ─────────────────────────────────────────────────────────
function para(children, opts = {}) {
  const cfg = {
    spacing: { before: opts.before ?? 40, after: opts.after ?? 40 },
    alignment: opts.align || AlignmentType.LEFT,
    children: Array.isArray(children) ? children : [children],
  };
  if (opts.heading)   cfg.heading   = opts.heading;
  if (opts.numbering) cfg.numbering = opts.numbering;
  if (opts.indent)    cfg.indent    = opts.indent;
  if (opts.border)    cfg.border    = opts.border;
  return new Paragraph(cfg);
}

function spacer(n = 80) {
  return para([run('')], { before: 0, after: n });
}

function divider(color = C.accent) {
  return para([run('')], {
    before: 0, after: 0,
    border: { bottom: { style: BorderStyle.SINGLE, size: 6, color, space: 1 } },
  });
}

// ── Table cell helper ─────────────────────────────────────────────────────────
function cell(paragraphs, opts = {}) {
  const w = opts.width ?? 4680;
  const cfg = {
    width: { size: w, type: WidthType.DXA },
    margins: opts.margins ?? CM,
    verticalAlign: opts.vAlign ?? VerticalAlign.TOP,
    children: Array.isArray(paragraphs) ? paragraphs : [paragraphs],
  };
  // Only set borders if explicitly provided — avoids table-level/cell-level conflicts
  if (opts.borders !== undefined) cfg.borders = opts.borders;
  if (opts.shading)  cfg.shading  = { fill: opts.shading, type: ShadingType.CLEAR };
  return new TableCell(cfg);
}

// Header cell (dark background, white bold text)
function hCell(text, width, bg = C.rowHdr) {
  return cell(
    [para([run(text, { bold: true, color: C.white, size: 18 })], { before: 0, after: 0 })],
    { width, shading: bg, borders: BORDERS_ALL(C.border), margins: CM_SM }
  );
}

// Data cell (optional alt-row shading)
function dCell(text, width, shade) {
  return cell(
    [para([run(text, { size: 18 })], { before: 0, after: 0 })],
    { width, shading: shade || null, borders: BORDERS_ALL(C.border), margins: CM_SM }
  );
}

// Invisible cell (questionnaire layout — no visible borders)
function qCell(paragraphs, width, shade) {
  return cell(paragraphs, {
    width,
    borders: BORDERS_ALL(C.border, 4),
    shading: shade || null,
    margins: CM,
  });
}

// ── Page number using SimpleField (proper OOXML, not deprecated w:pgNum) ──────
function pageNumRun() {
  // SimpleField wraps an instrText for PAGE — this generates proper fldChar XML
  return new SimpleField('PAGE');
}

// ── Cover page ────────────────────────────────────────────────────────────────
function buildCover() {
  const now = new Date().toLocaleDateString('en-US', {
    year: 'numeric', month: 'long', day: 'numeric',
  });
  return [
    spacer(1440),
    para([
      run('H', { bold: true, size: 120, color: C.red }),
      run('  HUNTER', { bold: true, size: 80, color: C.navy }),
    ], { align: AlignmentType.CENTER, before: 0, after: 60 }),
    para([run('THREAT HUNT PLAN', { bold: true, size: 40, color: C.accent })],
      { align: AlignmentType.CENTER, before: 0, after: 40 }),
    divider(C.accent),
    spacer(200),
    para([run(`Generated: ${now}`, { size: 22, color: C.muted })],
      { align: AlignmentType.CENTER }),
    para([run(
      `Modules: ${plan.total_modules}  ·  Hunt Actions: ${plan.total_hunt_actions}  ·  Questions: ${plan.total_questions}`,
      { bold: true, size: 22, color: C.navy }
    )], { align: AlignmentType.CENTER }),
    spacer(300),
    para([run('SENSITIVE  //  HUNT OPERATIONS', { bold: true, size: 18, color: C.red })],
      { align: AlignmentType.CENTER }),
    para([new PageBreak()], { before: 0, after: 0 }),
  ];
}

// ── Executive summary ─────────────────────────────────────────────────────────
function buildSummary() {
  const now = new Date().toLocaleDateString('en-US', {
    year: 'numeric', month: 'long', day: 'numeric',
  });
  const totalHours = plan.modules.reduce((s, m) => s + (m.estimated_hours || 0), 0);
  const allMitre   = [...new Set(plan.modules.flatMap(m => m.mitre_techniques || []))];

  const statsTable = new Table({
    width: { size: 9360, type: WidthType.DXA },
    columnWidths: [2340, 2340, 2340, 2340],
    rows: [
      new TableRow({ children: [
        hCell('Modules',     2340),
        hCell('Hunt Steps',  2340),
        hCell('Questions',   2340),
        hCell('Est. Hours',  2340),
      ]}),
      new TableRow({ children: [
        dCell(String(plan.total_modules),       2340, C.rowAlt),
        dCell(String(plan.total_hunt_actions),  2340),
        dCell(String(plan.total_questions),     2340, C.rowAlt),
        dCell(`${totalHours}h`,                 2340),
      ]}),
    ],
  });

  return [
    para([run('Executive Summary', { bold: true, size: 32, color: C.navy })],
      { heading: HeadingLevel.HEADING_1 }),
    divider(),
    spacer(60),
    para([run(
      `This document presents the Threat Hunt Plan generated by HUNTER on ${now}. ` +
      `The plan consists of ${plan.total_modules} hunt module(s) executed in the ` +
      `sequence defined below, encompassing ${plan.total_hunt_actions} specific hunt ` +
      `steps and ${plan.total_questions} pre-hunt questionnaire items.`,
      { size: 20 }
    )], { before: 0, after: 120 }),
    statsTable,
    spacer(100),
    para([
      run('MITRE ATT&CK Coverage:  ', { bold: true, size: 18, color: C.navy }),
      run(allMitre.length ? allMitre.join('  ') : 'None mapped', { size: 18, color: C.muted }),
    ], { before: 0, after: 60 }),
    para([run('Module Execution Order', { bold: true, size: 22, color: C.navy })],
      { before: 60, after: 40 }),
    ...plan.modules.map(m => {
      const pc = PRIO_COLORS[m.priority] || PRIO_COLORS.High;
      return para([
        run(`Step ${m.step}:  `, { bold: true, size: 20, color: C.navy }),
        run(m.name, { size: 20 }),
        run(`   [${m.priority || 'High'}]`, { bold: true, size: 18, color: pc }),
        run(`   ~${m.estimated_hours || 0}h`, { size: 18, color: C.muted }),
      ], { before: 20, after: 20 });
    }),
    spacer(60),
    para([new PageBreak()], { before: 0, after: 0 }),
  ];
}

// ── Module section ────────────────────────────────────────────────────────────
function buildModule(mod) {
  const isApt = mod.category === 'APT';
  const pc    = PRIO_COLORS[mod.priority] || PRIO_COLORS.High;
  const hCol  = isApt ? C.apt : C.navy;
  const out   = [];

  // Title
  out.push(divider(isApt ? C.apt : C.accent));
  out.push(para([
    run(`STEP ${mod.step}  `, { bold: true, size: 26, color: C.accent }),
    run(mod.name.toUpperCase(), { bold: true, size: 26, color: hCol }),
  ], { before: 100, after: 40 }));
  out.push(divider(isApt ? C.apt : C.accent));

  if (isApt) {
    out.push(para([run('NATION STATE THREAT ACTOR MODULE', { bold: true, size: 18, color: C.apt })],
      { before: 40, after: 20 }));
  }

  // Metadata table
  const metaRows = [
    ['Category',    mod.category || 'General'],
    ['Priority',    mod.priority || 'High'],
    ['Author',      mod.author || 'Unknown'],
    ['Updated',     mod.last_updated || 'N/A'],
    ['Est. Hours',  `~${mod.estimated_hours || 0}h`],
    ['Hunt Steps',  String((mod.hunt_actions || []).reduce((s, g) => s + g.actions.length, 0))],
    ['Questions',   String((mod.questions || []).length)],
  ].map(([label, value], i) => new TableRow({ children: [
    hCell(label, 2400),
    dCell(value, 6960, i % 2 === 0 ? C.rowAlt : null),
  ]}));

  out.push(spacer(40));
  out.push(new Table({
    width: { size: 9360, type: WidthType.DXA },
    columnWidths: [2400, 6960],
    rows: metaRows,
  }));
  out.push(spacer(60));

  // Tags
  if ((mod.tags || []).length) {
    out.push(para([
      run('Tags:  ', { bold: true, size: 18, color: C.muted }),
      run(mod.tags.join('  ·  '), { size: 18, color: C.muted }),
    ], { before: 0, after: 40 }));
  }

  // MITRE
  if ((mod.mitre_techniques || []).length) {
    out.push(para([
      run('MITRE ATT&CK:  ', { bold: true, size: 18, color: C.mitre }),
      run(mod.mitre_techniques.join('  '), { size: 18, color: C.mitre }),
    ], { before: 0, after: 60 }));
  }

  // Prerequisites
  if ((mod.prerequisites || []).length) {
    out.push(para([run('PREREQUISITES', { bold: true, size: 20, color: C.amber })],
      { before: 80, after: 20,
        border: { bottom: { style: BorderStyle.SINGLE, size: 2, color: 'D97706', space: 1 } } }));
    mod.prerequisites.forEach(p => {
      out.push(para([
        run('  ', { size: 18 }),
        run(p, { size: 18, color: '374151' }),
      ], { before: 20, after: 10, indent: { left: 240 } }));
    });
    out.push(spacer(40));
  }

  // Required tools — each on its own clean line, no side-by-side packing
  if ((mod.required_tools || []).length) {
    out.push(para([run('REQUIRED TOOLS', { bold: true, size: 20, color: C.navy })],
      { before: 80, after: 20,
        border: { bottom: { style: BorderStyle.SINGLE, size: 2, color: C.accent, space: 1 } } }));
    mod.required_tools.forEach(t => {
      out.push(para([run(t, { size: 18 })],
        { before: 20, after: 10, indent: { left: 360 } }));
    });
    out.push(spacer(40));
  }

  // Hunt actions
  out.push(para([run('HUNT ACTIONS', { bold: true, size: 22, color: isApt ? C.apt : C.success })],
    { before: 80, after: 20,
      border: { bottom: { style: BorderStyle.SINGLE, size: 4,
        color: isApt ? C.apt : C.success, space: 1 } } }));

  (mod.hunt_actions || []).forEach((group, gi) => {
    out.push(para([run(`${gi + 1}.  ${group.title}`, { bold: true, size: 20, color: hCol })],
      { before: 60, after: 20 }));
    (group.actions || []).forEach((action, ai) => {
      out.push(para([
        run(`${ai + 1}.  `, { bold: true, size: 17, color: C.muted }),
        run(action, { size: 17, font: 'Courier New' }),
      ], { before: 20, after: 20, indent: { left: 360 } }));
    });
  });
  out.push(spacer(60));

  // References
  if ((mod.references || []).length) {
    out.push(para([run('References', { bold: true, size: 18, color: C.muted })],
      { before: 40, after: 10 }));
    mod.references.forEach(r => {
      out.push(para([run(r, { size: 16, color: C.accent })],
        { before: 0, after: 10, indent: { left: 240 } }));
    });
  }

  out.push(spacer(40));
  out.push(para([new PageBreak()], { before: 0, after: 0 }));
  return out;
}

// ── Questionnaire ─────────────────────────────────────────────────────────────
function buildQuestionnaire() {
  const out = [];
  out.push(para([run('Pre-Hunt Questionnaire', { bold: true, size: 32, color: C.navy })],
    { heading: HeadingLevel.HEADING_1 }));
  out.push(divider());
  out.push(spacer(60));
  out.push(para([run(
    'Complete the following items with the mission partner prior to or at the ' +
    'outset of the engagement. Accurate responses ensure hunt actions are performed ' +
    'safely, within authorized scope, and with appropriate tooling available.',
    { size: 20 }
  )], { before: 0, after: 100 }));

  let qNum = 1;
  plan.modules.forEach(mod => {
    if (!(mod.questions || []).length) return;
    out.push(para([run(mod.name.toUpperCase(), { bold: true, size: 22, color: C.navy })],
      { before: 120, after: 20,
        border: { bottom: { style: BorderStyle.SINGLE, size: 3, color: C.accent, space: 1 } } }));
    out.push(spacer(40));

    mod.questions.forEach(q => {
      const qTable = new Table({
        width: { size: 9360, type: WidthType.DXA },
        columnWidths: [640, 8720],
        rows: [
          new TableRow({ children: [
            // Q number badge
            cell(
              [para([run(`Q${String(qNum).padStart(2, '0')}`, { bold: true, color: C.white, size: 18 })],
                { before: 0, after: 0, align: AlignmentType.CENTER })],
              { width: 640, shading: C.rowHdr, borders: BORDERS_ALL(C.border), margins: CM_SM }
            ),
            // Question text
            cell(
              [para([run(q, { size: 20 })], { before: 0, after: 0 })],
              { width: 8720, borders: BORDERS_ALL(C.border) }
            ),
          ]}),
          new TableRow({ children: [
            // ANS label
            cell(
              [para([run('ANS', { bold: true, color: C.muted, size: 14 })],
                { before: 0, after: 0, align: AlignmentType.CENTER })],
              { width: 640, shading: 'F3F4F6', borders: BORDERS_ALL(C.border), margins: CM_SM }
            ),
            // Answer space (3 blank lines)
            cell(
              [spacer(0), spacer(0), spacer(0)],
              { width: 8720, shading: 'FAFAFA', borders: BORDERS_ALL(C.border) }
            ),
          ]}),
        ],
      });
      out.push(qTable);
      out.push(spacer(60));
      qNum++;
    });
  });
  return out;
}

// ── Header ────────────────────────────────────────────────────────────────────
function buildHeader() {
  return new Header({ children: [
    para([
      run('H  HUNTER', { bold: true, size: 18, color: C.red }),
      run('   —   THREAT HUNT PLAN', { size: 16, color: C.muted }),
      run('          SENSITIVE // HUNT OPERATIONS', { size: 14, color: C.muted }),
    ], {
      before: 0, after: 80,
      border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: C.accent, space: 1 } },
    }),
  ]});
}

// ── Footer — uses SimpleField for page number ─────────────────────────────────
function buildFooter() {
  // SimpleField('PAGE') generates a proper OOXML field instruction,
  // which is what modern Word expects instead of deprecated <w:pgNum/>
  return new Footer({ children: [
    para([
      run(`HUNTER  |  ${new Date().toLocaleDateString()}  |  Page `,
        { size: 16, color: C.muted }),
      new SimpleField('PAGE'),
    ], {
      before: 60, after: 0,
      border: { top: { style: BorderStyle.SINGLE, size: 2, color: C.border, space: 1 } },
    }),
  ]});
}

// ── Assemble document ─────────────────────────────────────────────────────────
async function build() {
  const children = [
    ...buildCover(),
    ...buildSummary(),
    ...plan.modules.flatMap(m => buildModule(m)),
    ...buildQuestionnaire(),
  ];

  const doc = new Document({
    numbering: { config: [{
      reference: 'bullets',
      levels: [{
        level: 0, format: LevelFormat.BULLET, text: '\u2022',
        alignment: AlignmentType.LEFT,
        style: { paragraph: { indent: { left: 720, hanging: 360 } } },
      }],
    }]},
    styles: {
      default: { document: { run: { font: 'Arial', size: 20 } } },
      paragraphStyles: [
        { id: 'Heading1', name: 'Heading 1', basedOn: 'Normal', next: 'Normal',
          quickFormat: true,
          run: { size: 32, bold: true, color: C.navy, font: 'Arial' },
          paragraph: { spacing: { before: 240, after: 120 }, outlineLevel: 0 } },
        { id: 'Heading2', name: 'Heading 2', basedOn: 'Normal', next: 'Normal',
          quickFormat: true,
          run: { size: 26, bold: true, color: C.accent, font: 'Arial' },
          paragraph: { spacing: { before: 180, after: 80 }, outlineLevel: 1 } },
      ],
    },
    sections: [{
      properties: {
        page: {
          size: { width: 12240, height: 15840 },
          margin: { top: 1008, right: 1008, bottom: 1008, left: 1008 },
        },
      },
      headers: { default: buildHeader() },
      footers: { default: buildFooter() },
      children,
    }],
  });

  const buffer = await Packer.toBuffer(doc);
  fs.writeFileSync(outPath, buffer);
  console.log(`Exported: ${outPath}  (${buffer.length} bytes)`);
}

build().catch(err => {
  console.error('Export failed:', err.message || err);
  process.exit(1);
});
