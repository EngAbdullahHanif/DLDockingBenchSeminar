#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
convert_seminar_to_karmadock.py

Seminar data layout -> KarmaDock layout.

Seminar:  <src_dir>/<id>_ligand_refined.sdf , <src_dir>/<id>_protein_refined.pdb
KarmaDock: <out_dir>/<id>/<id>_ligand.sdf , <out_dir>/<id>/<id>_protein.pdb

The id is the ligand filename with '_ligand_refined.sdf' stripped, which is
exactly what KarmaDock's pre_processing.py / generate_graph.py expect.
"""
import argparse
import os
import shutil
import sys

import pandas as pd


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True, help="seminar CSV (e.g. proto_train.csv)")
    ap.add_argument("--src_dir", required=True, help="dir with the refined .sdf/.pdb files")
    ap.add_argument("--out_dir", required=True, help="output KarmaDock-layout dir")
    args = ap.parse_args()

    for path in (args.csv, args.src_dir):
        if not os.path.exists(path):
            sys.exit(f"ERROR: not found: {path}")

    os.makedirs(args.out_dir, exist_ok=True)
    df = pd.read_csv(args.csv)
    ok = miss = 0
    for _, row in df.iterrows():
        lig, prot = row["ligand_file_name"], row["protein_file_name"]
        cid = lig.replace("_ligand_refined.sdf", "")
        s_lig, s_prot = os.path.join(args.src_dir, lig), os.path.join(args.src_dir, prot)
        if not (os.path.exists(s_lig) and os.path.exists(s_prot)):
            miss += 1
            continue
        d = os.path.join(args.out_dir, cid)
        os.makedirs(d, exist_ok=True)
        shutil.copy2(s_lig, os.path.join(d, f"{cid}_ligand.sdf"))
        shutil.copy2(s_prot, os.path.join(d, f"{cid}_protein.pdb"))
        ok += 1
    print(f"converted {ok}/{len(df)} complexes ({miss} missing source files)")


if __name__ == "__main__":
    main()
