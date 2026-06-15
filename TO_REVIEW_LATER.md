# TO REVIEW LATER — deferred items & context

Running list of things we consciously deferred, with enough context to pick them up cold.
(Most recent first. Date format: 2026-06-13.)

---

## 1. Add the data-leakage caveat to `analysis_and_comparison.ipynb`  ← the main "remind me" item
**Status:** deferred (you asked to be reminded; doing the BDB2020+ eval first).

**Context — why this matters.** When we ran **P4 (LP-finetune) inference on `lp_test`** we got
**success@2Å = 94.5%, median 0.98 Å** — implausibly high (the KarmaDock paper's core-set ceiling
is 89.1%, and the same released model scores only ~56% on `proto_test`).

**Root cause = leakage.** All LP-test complexes are PDBBind v2020 refined/general/core
(1240/823/108) — the exact data the **released `karmadock_screening.pkl` was pretrained on**. So
any model that *starts from the released weights* (P1 baseline, P4 LP-finetune) has already seen
every LP-test complex → memorization, not generalization. LP-PDBBind's leak-proofing only holds
for models trained **from scratch** on LP-train (which is why the LP paper retrains every scoring
function from scratch).

**Consequence (the corrected experiment design):**
- `lp_test` is a **valid** leak-proof test **only for P5** (from scratch on LP-train; never saw lp_test).
- For released-weights models (**P1, P4**) the honest external test is **BDB2020+** (BindingDB
  post-2020, deposited after PDBBind v2020 → unseen). That eval is being built now (item moved to
  RUN_JOURNAL / tasks).

**What to add to the notebook when we resume:**
- A markdown caveat near the paper-comparison / metrics sections stating the above.
- Flag the **P4 (and P1) `lp_test`** rows as **LEAKED — not a generalization number** (keep them, but
  labelled; they're a clean *illustration* of the leakage the LP exercise targets).
- Mark **P5 `lp_test`** as the valid leak-proof number, and **P1/P4 BDB2020+** as their honest test.
- Note: the notebook's existing "leakage" cell measures *train/test PDB-id overlap within a split*
  (0 for both proto and LP) — it does NOT capture this *pretraining* leakage, so the caveat is needed.

---

## 2. GitHub repo push — security review before sharing
**Status:** deferred until the project is finished (repo is private for now).
- Target repo: `git@github.com:a-lamloum/BDLDT-Seminar.git`.
- **MUST rotate/revoke** the real W&B API key hardcoded in `scripts/run_train.sh` (deprecated script)
  before any share — treat as compromised.
- Exclude from any public push: `.claude/`, `SESSION_HANDOFF.md`; sanitize `RUN_JOURNAL.md`/`HANDOFF.md`
  (cluster host/user, no passwords); never commit datasets, checkpoints, the conda env tarball.
- Proposed curated structure is captured in the chat transcript (docs/, scripts/, condor/, docker/,
  notebooks/, data/ with a download script, no data).

---

## 3. (add new deferred items here as they arise)

## 4. (BONUS) Proper docking-result visualization (paper Fig. 1a style)
**Status:** deferred — the quick attempts (matplotlib 3D overlays + a py3Dmol surface cell) were
not good enough; removed. Redo later if useful.

**Idea:** make ONE publication-quality "docking result" figure like KarmaDock paper Fig. 1a:
protein pocket **surface** + ligand, panels for protein / ligand / before-docking / docking /
after-docking / complex, with the crystal vs KarmaDock predicted pose. Good example to use:
`4jdf_SPD_A_401` (best-of-3 RMSD 0.68 A) or any low-RMSD proto_test complex.

**How (tools):** py3Dmol renders interactively in a notebook but is hard to export to a clean
static PNG headless. For the paper look, render with **PyMOL** (e.g. `pip install pymol-open-source`
or a machine that has PyMOL/ChimeraX): load `<id>_protein_refined.pdb` + crystal
`<id>_ligand_refined.sdf` + our `results/.../<id>_pred.sdf` top pose, `show surface`, ray-trace,
`png`. Data is all present (proto_test structures + our predicted poses).
