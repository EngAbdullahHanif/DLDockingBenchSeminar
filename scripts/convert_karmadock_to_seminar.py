#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
convert_karmadock_to_seminar.py

KarmaDock docking output -> seminar results layout.

KarmaDock's ligand_docking.py writes, per repeat re in {0,1,2}:
    <input_dir>/<re>.csv                      (pdb_id, score, RMSD, FF_RMSD, Aligned_RMSD)
    <input_dir>/<re>/<id>_pred_<mode>.sdf     (mode in uncorrected|ff_corrected|align_corrected)

The seminar evaluator wants one ranked multi-conformer file per complex:
    <out_dir>/<id>_pred.sdf   (best pose first)

We rank repeats by MDN score (higher = better) and write their poses in order.
"""
import argparse
import os
import sys

import pandas as pd
from rdkit import Chem


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input_dir", required=True, help="KarmaDock out_dir (has 0.csv, 0/, ...)")
    ap.add_argument("--csv", required=True, help="seminar CSV listing the complexes")
    ap.add_argument("--out_dir", required=True, help="seminar results dir")
    ap.add_argument("--mode", default="align_corrected",
                    choices=["uncorrected", "ff_corrected", "align_corrected"],
                    help="which corrected pose to export (paper recommends FF/align correction)")
    ap.add_argument("--n_repeat", type=int, default=3)
    args = ap.parse_args()

    for path in (args.csv, args.input_dir):
        if not os.path.exists(path):
            sys.exit(f"ERROR: not found: {path}")
    os.makedirs(args.out_dir, exist_ok=True)

    # collect per-complex scores across repeats
    scores = {}
    repeats = []
    for re in range(args.n_repeat):
        csv_path = os.path.join(args.input_dir, f"{re}.csv")
        if not os.path.exists(csv_path):
            continue
        repeats.append(re)
        for _, row in pd.read_csv(csv_path).iterrows():
            scores.setdefault(row["pdb_id"], []).append({"repeat": re, "score": float(row["score"])})
    if not repeats:
        sys.exit("ERROR: no <re>.csv files found in input_dir")

    df = pd.read_csv(args.csv)
    ok = 0
    for _, row in df.iterrows():
        cid = row["ligand_file_name"].replace("_ligand_refined.sdf", "")
        ranked = sorted(scores.get(cid, [{"repeat": r, "score": 0.0} for r in repeats]),
                        key=lambda x: x["score"], reverse=True)   # higher MDN score first
        out_path = os.path.join(args.out_dir, f"{cid}_pred.sdf")
        writer = Chem.SDWriter(out_path)
        written = 0
        for info in ranked:
            re = info["repeat"]
            pose = os.path.join(args.input_dir, str(re), f"{cid}_pred_{args.mode}.sdf")
            if not os.path.exists(pose) and args.mode != "uncorrected":
                pose = os.path.join(args.input_dir, str(re), f"{cid}_pred_uncorrected.sdf")
            if not os.path.exists(pose):
                continue
            for mol in Chem.SDMolSupplier(pose, removeHs=False):
                if mol is None:
                    continue
                mol.SetProp("KarmaDock_Score", f"{info['score']:.4f}")
                mol.SetProp("KarmaDock_Repeat", str(re))
                mol.SetProp("KarmaDock_Mode", args.mode)
                writer.write(mol)
                written += 1
        writer.close()
        if written:
            ok += 1
        elif os.path.exists(out_path):
            os.remove(out_path)
    print(f"wrote {ok}/{len(df)} predicted-pose files to {args.out_dir}")


if __name__ == "__main__":
    main()
