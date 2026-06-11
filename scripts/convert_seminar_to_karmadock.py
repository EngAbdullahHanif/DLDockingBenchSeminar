#!/usr/bin/env python3
import os
import sys
import argparse
import pandas as pd
import shutil

def main():
    parser = argparse.ArgumentParser(description="Convert seminar dataset format to KarmaDock expected structure.")
    parser.add_argument("--csv", required=True, help="Path to the dataset CSV file (e.g. proto_test.csv)")
    parser.add_argument("--src_dir", required=True, help="Directory containing the raw files (e.g. proto_test/)")
    parser.add_argument("--out_dir", required=True, help="Output directory to create the KarmaDock structure")
    args = parser.parse_args()

    if not os.path.exists(args.csv):
        print(f"Error: CSV file not found: {args.csv}")
        sys.exit(1)
    if not os.path.exists(args.src_dir):
        print(f"Error: Source directory not found: {args.src_dir}")
        sys.exit(1)

    os.makedirs(args.out_dir, exist_ok=True)
    df = pd.read_csv(args.csv)

    print(f"Loaded CSV with {len(df)} entries.")
    success_count = 0
    missing_count = 0

    for idx, row in df.iterrows():
        lig_file = row['ligand_file_name']
        prot_file = row['protein_file_name']
        
        # Derive complex ID (e.g., from 3ix2_AC2_A_302_ligand_refined.sdf -> 3ix2_AC2_A_302)
        complex_id = lig_file.replace('_ligand_refined.sdf', '')
        
        # Paths
        src_lig_path = os.path.join(args.src_dir, lig_file)
        src_prot_path = os.path.join(args.src_dir, prot_file)
        
        dest_complex_dir = os.path.join(args.out_dir, complex_id)
        dest_lig_path = os.path.join(dest_complex_dir, f"{complex_id}_ligand.sdf")
        dest_prot_path = os.path.join(dest_complex_dir, f"{complex_id}_protein.pdb")

        if not os.path.exists(src_lig_path) or not os.path.exists(src_prot_path):
            print(f"Warning: Missing source files for {complex_id}. Ligand exists: {os.path.exists(src_lig_path)}, Protein exists: {os.path.exists(src_prot_path)}")
            missing_count += 1
            continue

        os.makedirs(dest_complex_dir, exist_ok=True)
        shutil.copy2(src_lig_path, dest_lig_path)
        shutil.copy2(src_prot_path, dest_prot_path)
        success_count += 1

    print(f"Conversion complete. Successfully converted {success_count}/{len(df)} complexes. {missing_count} had missing source files.")

if __name__ == "__main__":
    main()
