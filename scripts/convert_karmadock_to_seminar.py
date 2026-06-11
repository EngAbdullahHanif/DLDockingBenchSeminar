#!/usr/bin/env python3
import os
import sys
import argparse
import pandas as pd
from rdkit import Chem

def main():
    parser = argparse.ArgumentParser(description="Convert KarmaDock outputs to seminar format.")
    parser.add_argument("--input_dir", required=True, help="Directory containing KarmaDock results (0.csv, 0/, etc.)")
    parser.add_argument("--csv", required=True, help="Path to original seminar CSV (to list complex IDs)")
    parser.add_argument("--out_dir", required=True, help="Target directory for seminar predicted SDFs")
    parser.add_argument("--mode", default="align_corrected", choices=["uncorrected", "ff_corrected", "align_corrected"],
                        help="Which KarmaDock output pose to use (default: align_corrected)")
    args = parser.parse_args()

    if not os.path.exists(args.csv):
        print(f"Error: CSV file not found: {args.csv}")
        sys.exit(1)
    if not os.path.exists(args.input_dir):
        print(f"Error: Input directory not found: {args.input_dir}")
        sys.exit(1)

    os.makedirs(args.out_dir, exist_ok=True)
    df = pd.read_csv(args.csv)
    
    # Read scores from the repeats
    scores = {}
    repeats = []
    for re in range(3):
        csv_path = os.path.join(args.input_dir, f"{re}.csv")
        if os.path.exists(csv_path):
            df_re = pd.read_csv(csv_path)
            for _, row in df_re.iterrows():
                pdb_id = row['pdb_id']
                if pdb_id not in scores:
                    scores[pdb_id] = []
                scores[pdb_id].append({
                    'repeat': re,
                    'score': row['score']
                })
            repeats.append(re)
    
    if not repeats:
        print("Error: No repeat CSV files (0.csv, 1.csv, etc.) found in input_dir.")
        sys.exit(1)

    print(f"Found {len(repeats)} repeat results. Processing {len(df)} complexes...")

    success_count = 0
    
    for idx, row in df.iterrows():
        lig_file = row['ligand_file_name']
        complex_id = lig_file.replace('_ligand_refined.sdf', '')
        
        # Sort repeats by score (lower score / higher affinity/likelihood)
        # Note: For KarmaDock, higher score is better.
        if complex_id in scores:
            complex_scores = sorted(scores[complex_id], key=lambda x: x['score'], reverse=True)
        else:
            # Fallback if not in CSV: just use repeats in order
            complex_scores = [{'repeat': r, 'score': 0.0} for r in repeats]

        # Gather conformers across the sorted repeats
        writer_path = os.path.join(args.out_dir, f"{complex_id}_pred.sdf")
        writer = Chem.SDWriter(writer_path)
        
        conformers_written = 0
        for info in complex_scores:
            re = info['repeat']
            score = info['score']
            
            # File name pattern in KarmaDock
            # e.g., 0/3ix2_AC2_A_302_pred_align_corrected.sdf
            pose_file = f"{complex_id}_pred_{args.mode}.sdf"
            pose_path = os.path.join(args.input_dir, str(re), pose_file)
            
            # If specified mode fails or is not found, fallback to uncorrected
            if not os.path.exists(pose_path) and args.mode != "uncorrected":
                fallback_file = f"{complex_id}_pred_uncorrected.sdf"
                pose_path = os.path.join(args.input_dir, str(re), fallback_file)
                
            if os.path.exists(pose_path):
                suppl = Chem.SDMolSupplier(pose_path, removeHs=False)
                for mol in suppl:
                    if mol is not None:
                        # Set score property in SDF
                        mol.SetProp("KarmaDock_Score", f"{score:.4f}")
                        mol.SetProp("KarmaDock_Repeat", str(re))
                        mol.SetProp("KarmaDock_Mode", args.mode)
                        writer.write(mol)
                        conformers_written += 1
                        
        writer.close()
        if conformers_written > 0:
            success_count += 1
        else:
            # Remove empty file
            if os.path.exists(writer_path):
                os.remove(writer_path)
            print(f"Warning: No predicted poses found for {complex_id}")

    print(f"Finished. Successfully wrote {success_count}/{len(df)} output files to {args.out_dir}")

if __name__ == "__main__":
    main()
