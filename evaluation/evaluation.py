#!/usr/bin/env python3
"""
updated_evaluation.py — Updated evaluation script for pocket-conditioned molecular docking tools.

This script evaluates docking predictions against reference structures using CSV-based dataset mapping.
Supports multiple dataset variants (proto_test, posebusters_filtered, full_test) with different naming conventions.

Computes symmetry-corrected heavy-atom RMSD and runs PoseBusters physical validity checks.

Required packages:
    pip install posebusters rdkit-pypi numpy pandas

Dataset Structure:
    data/{dataset_name}.csv - Contains protein-ligand mappings
    data/{dataset_name}/ - Directory with reference protein and ligand files
    results/{dataset_name}/ - Directory for predicted poses

Expected CSV formats:
    proto_test.csv/full_test.csv: ligand_file_name,protein_file_name,Year,Log Binding Affinity,Binding Affinity Measurement,PDBID
    posebusters_filtered.csv: ligand_name,ligand_file,protein_file

Predicted pose naming format:
    results/{dataset_name}/{complex_identifier}_pred.sdf

    Where complex_identifier is derived from ligand filename:
    - proto_test/full_test: "3ix2_AC2_A_302" (from "3ix2_AC2_A_302_ligand_refined.sdf")
    - posebusters_filtered: "5SAK_ZRY" (from "5SAK_ZRY_ligand.sdf")

Usage:
    Run from the repository root directory:

    # Evaluate proto_test dataset (default: top-1 pose, PoseBusters validation enabled)
    python evaluation/evaluation.py --dataset proto_test

    # Evaluate with RMSD only (skip PoseBusters validation)
    python evaluation/evaluation.py --dataset proto_test --no_pb_valid

    # Evaluate multiple poses
    python evaluation/evaluation.py --dataset full_test --top_n 5

    # Custom output path
    python evaluation/evaluation.py --dataset full_test --output_csv results/my_eval.csv
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from rdkit import Chem
from rdkit.Chem import AllChem, rdMolAlign

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# RMSD Calculation
# ---------------------------------------------------------------------------

def calc_symmetry_rmsd(pred_mol: Chem.Mol, ref_mol: Chem.Mol) -> float:
    """
    Compute symmetry-corrected heavy-atom RMSD between predicted and reference mol.

    Uses RDKit's GetBestRMS which accounts for molecular symmetry.
    """
    try:
        pred_noH = AllChem.RemoveHs(pred_mol)
        ref_noH = AllChem.RemoveHs(ref_mol)
        rmsd = rdMolAlign.GetBestRMS(pred_noH, ref_noH)
        return rmsd
    except Exception as e:
        logger.warning(f"RMSD calculation failed: {e}")
        return float("nan")


# ---------------------------------------------------------------------------
# Molecule Loading
# ---------------------------------------------------------------------------

def load_pred_poses(sdf_path: Path, top_n: int) -> List[Chem.Mol]:
    """Load up to top_n conformers from a multi-conformer SDF file."""
    if not sdf_path.exists():
        return []

    supplier = Chem.SDMolSupplier(str(sdf_path), removeHs=False, sanitize=False)
    poses = []
    for i, mol in enumerate(supplier):
        if i >= top_n:
            break
        if mol is not None:
            poses.append(mol)
        else:
            logger.warning(f"  Pose {i+1} in {sdf_path.name} could not be parsed, skipping.")
    return poses


def load_ref_ligand(sdf_path: Path) -> Optional[Chem.Mol]:
    """Load single-conformer reference ligand from SDF."""
    if not sdf_path.exists():
        return None

    supplier = Chem.SDMolSupplier(str(sdf_path), removeHs=False, sanitize=False)
    for mol in supplier:
        if mol is not None:
            return mol
    return None


# ---------------------------------------------------------------------------
# Dataset Handling
# ---------------------------------------------------------------------------

def get_complex_identifier(ligand_filename: str, dataset_name: str) -> str:
    """Extract complex identifier from ligand filename based on dataset naming convention."""
    if dataset_name in ["proto_test", "full_test", "proto_train", "full_train"]:
        # Format: "3ix2_AC2_A_302_ligand_refined.sdf" -> "3ix2_AC2_A_302"
        return ligand_filename.replace("_ligand_refined.sdf", "")
    elif dataset_name == "posebusters_filtered":
        # Format: "5SAK_ZRY_ligand.sdf" -> "5SAK_ZRY"
        return ligand_filename.replace("_ligand.sdf", "")
    else:
        # Fallback: remove common suffixes
        for suffix in ["_ligand_refined.sdf", "_ligand.sdf", ".sdf"]:
            if ligand_filename.endswith(suffix):
                return ligand_filename.replace(suffix, "")
        return ligand_filename


def load_dataset_csv(csv_path: Path) -> pd.DataFrame:
    """Load and standardize dataset CSV file."""
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    df = pd.read_csv(csv_path)

    # Standardize column names based on dataset type
    if "ligand_file_name" in df.columns:
        # proto_test/full_test format
        df = df.rename(columns={
            "ligand_file_name": "ligand_file",
            "protein_file_name": "protein_file"
        })
    elif "ligand_name" in df.columns:
        # posebusters_filtered format - already has correct column names
        pass
    else:
        raise ValueError(f"Unrecognized CSV format in {csv_path}")

    return df


def get_file_paths(row: pd.Series, dataset_name: str, data_dir: Path, results_dir: Path) -> Tuple[Path, Path, Path]:
    """Get file paths for reference protein, reference ligand, and predicted poses."""
    ligand_file = row["ligand_file"]
    protein_file = row["protein_file"]

    # Reference files in data directory
    ref_ligand_path = data_dir / dataset_name / ligand_file
    ref_protein_path = data_dir / dataset_name / protein_file

    # Predicted poses in results directory
    complex_id = get_complex_identifier(ligand_file, dataset_name)
    pred_sdf_path = results_dir / dataset_name / f"{complex_id}_pred.sdf"

    return ref_protein_path, ref_ligand_path, pred_sdf_path


# ---------------------------------------------------------------------------
# PoseBusters Integration
# ---------------------------------------------------------------------------

def run_posebusters_check(pred_sdf: Path, ref_sdf: Path, protein_pdb: Path) -> pd.DataFrame:
    """Run PoseBusters validity checks on predicted poses."""
    try:
        from posebusters import PoseBusters

        buster = PoseBusters(config="dock")
        results = buster.bust(
            mol_pred=str(pred_sdf),
            mol_true=str(ref_sdf),
            mol_cond=str(protein_pdb),
        )
        return results
    except ImportError:
        logger.error("PoseBusters not installed. Install with: pip install posebusters")
        sys.exit(1)
    except Exception as e:
        logger.warning(f"PoseBusters check failed: {e}")
        return pd.DataFrame()


# ---------------------------------------------------------------------------
# Single Complex Evaluation
# ---------------------------------------------------------------------------

def evaluate_complex(
    row: pd.Series,
    dataset_name: str,
    data_dir: Path,
    results_dir: Path,
    top_n: int,
    run_pb: bool
) -> List[Dict]:
    """Evaluate all poses for a single complex."""

    # Get file paths
    ref_protein_path, ref_ligand_path, pred_sdf_path = get_file_paths(
        row, dataset_name, data_dir, results_dir
    )

    complex_id = get_complex_identifier(row["ligand_file"], dataset_name)

    # Check if files exist
    missing_files = []
    if not pred_sdf_path.exists():
        missing_files.append(f"predicted poses: {pred_sdf_path}")
    if not ref_ligand_path.exists():
        missing_files.append(f"reference ligand: {ref_ligand_path}")
    if run_pb and not ref_protein_path.exists():
        missing_files.append(f"reference protein: {ref_protein_path}")

    if missing_files:
        logger.warning(f"  [{complex_id}] Missing files: {', '.join(missing_files)}")
        return []

    # Load molecules
    ref_mol = load_ref_ligand(ref_ligand_path)
    if ref_mol is None:
        logger.warning(f"  [{complex_id}] Could not parse reference ligand")
        return []

    pred_poses = load_pred_poses(pred_sdf_path, top_n)
    if not pred_poses:
        logger.warning(f"  [{complex_id}] No valid predicted poses found")
        return []

    # Calculate RMSD for all poses
    results = []
    for rank, pose in enumerate(pred_poses, start=1):
        rmsd = calc_symmetry_rmsd(pose, ref_mol)

        result_row = {
            "complex_id": complex_id,
            "dataset": dataset_name,
            "pose_rank": rank,
            "rmsd": round(rmsd, 4) if not np.isnan(rmsd) else np.nan,
            "rmsd_lt2": rmsd < 2.0 if not np.isnan(rmsd) else False,
            "rmsd_lt1": rmsd < 1.0 if not np.isnan(rmsd) else False,
            "ligand_file": row["ligand_file"],
            "protein_file": row["protein_file"]
        }

        results.append(result_row)

    # Run PoseBusters checks if requested
    if run_pb:
        pb_results = run_posebusters_check(pred_sdf_path, ref_ligand_path, ref_protein_path)

        if not pb_results.empty:
            for rank_idx in range(min(len(results), len(pb_results))):
                pb_row = pb_results.iloc[rank_idx]

                # Calculate PB-Valid (all boolean tests pass)
                bool_cols = pb_row.index[pb_row.apply(lambda x: isinstance(x, (bool, np.bool_)))]
                pb_valid = bool(pb_row[bool_cols].all()) if len(bool_cols) > 0 else False
                results[rank_idx]["pb_valid"] = pb_valid

                # Add individual test results
                for col in bool_cols:
                    if col not in results[rank_idx]:
                        results[rank_idx][col] = bool(pb_row[col])
        else:
            for result_row in results:
                result_row["pb_valid"] = None

    return results


# ---------------------------------------------------------------------------
# Main Evaluation
# ---------------------------------------------------------------------------

def evaluate_dataset(
    dataset_name: str,
    data_dir: Path,
    results_dir: Path,
    top_n: int,
    run_pb: bool,
    output_csv: Optional[Path] = None
) -> pd.DataFrame:
    """Run evaluation on a complete dataset."""

    # Load dataset CSV
    csv_path = data_dir / f"{dataset_name}.csv"
    df = load_dataset_csv(csv_path)

    logger.info(f"Loaded {len(df)} complexes from {csv_path}")
    logger.info(f"Dataset: {dataset_name} | Top-N: {top_n} | PoseBusters: {run_pb}")

    all_results = []
    n_skipped = 0

    for i, (_, row) in enumerate(df.iterrows(), start=1):
        if i % 50 == 0 or i == len(df):
            logger.info(f"  Progress: {i}/{len(df)}")

        results = evaluate_complex(row, dataset_name, data_dir, results_dir, top_n, run_pb)
        if results:
            all_results.extend(results)
        else:
            n_skipped += 1

    if not all_results:
        logger.error("No results produced. Check your predicted poses and data paths.")
        return pd.DataFrame()

    results_df = pd.DataFrame(all_results)

    # Log summary statistics
    n_evaluated = results_df["complex_id"].nunique()
    logger.info(f"Evaluated {n_evaluated} complexes ({n_skipped} skipped)")

    # Top-1 statistics
    top1 = results_df[results_df["pose_rank"] == 1]
    if not top1.empty:
        rmsd_lt2_pct = top1["rmsd_lt2"].mean() * 100
        rmsd_lt1_pct = top1["rmsd_lt1"].mean() * 100
        median_rmsd = top1["rmsd"].median()

        logger.info(f"Top-1 Results:")
        logger.info(f"  RMSD < 2.0 Å: {rmsd_lt2_pct:.1f}%")
        logger.info(f"  RMSD < 1.0 Å: {rmsd_lt1_pct:.1f}%")
        logger.info(f"  Median RMSD: {median_rmsd:.2f} Å")

        if "pb_valid" in top1.columns:
            pb_valid_pct = top1["pb_valid"].mean() * 100
            logger.info(f"  PB-Valid: {pb_valid_pct:.1f}%")

    # Best-of-N statistics
    if top_n > 1 and not results_df.empty:
        best_poses = results_df.loc[results_df.groupby("complex_id")["rmsd"].idxmin()]
        best_lt2_pct = best_poses["rmsd_lt2"].mean() * 100
        best_lt1_pct = best_poses["rmsd_lt1"].mean() * 100

        logger.info(f"Best-of-{top_n} Results:")
        logger.info(f"  RMSD < 2.0 Å: {best_lt2_pct:.1f}%")
        logger.info(f"  RMSD < 1.0 Å: {best_lt1_pct:.1f}%")

        if "pb_valid" in best_poses.columns:
            best_pb_pct = best_poses["pb_valid"].mean() * 100
            logger.info(f"  PB-Valid: {best_pb_pct:.1f}%")

    # Save results
    if output_csv:
        output_csv.parent.mkdir(parents=True, exist_ok=True)
        results_df.to_csv(output_csv, index=False)
        logger.info(f"Results saved to {output_csv}")

    return results_df


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate docking predictions using CSV-based dataset mapping.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Evaluate proto_test dataset with default PoseBusters validation
  python evaluation.py --dataset proto_test

  # Evaluate with RMSD only (skip PoseBusters validation)
  python evaluation.py --dataset proto_test --no_pb_valid

  # Evaluate multiple poses
  python evaluation.py --dataset posebusters_filtered --top_n 5

Expected file structure (from repository root):
  data/{dataset}.csv                           # Dataset mapping file
  data/{dataset}/{ligand_file}                 # Reference ligand SDF
  data/{dataset}/{protein_file}                # Reference protein PDB
  results/{dataset}/{complex_id}_pred.sdf      # Predicted poses (ranked)
        """,
    )

    parser.add_argument(
        "--dataset",
        type=str,
        required=True,
        choices=["proto_test", "proto_train", "posebusters_filtered", "full_test", "full_train"],
        help="Dataset name to evaluate"
    )
    parser.add_argument(
        "--top_n",
        type=int,
        default=1,
        help="Number of ranked poses to evaluate per complex (default: 1)"
    )
    parser.add_argument(
        "--no_pb_valid",
        action="store_true",
        help="Skip PoseBusters physical validity checks (PB validation is enabled by default)"
    )
    parser.add_argument(
        "--output_csv",
        type=Path,
        default=None,
        help="Output CSV path (default: results/{dataset}_evaluation.csv)"
    )

    return parser.parse_args()


def main():
    args = parse_args()

    # Fixed paths
    data_dir = Path("data")
    results_dir = Path("results")

    # Validate paths
    if not data_dir.exists():
        logger.error(f"Data directory does not exist: {data_dir}")
        sys.exit(1)

    csv_path = data_dir / f"{args.dataset}.csv"
    if not csv_path.exists():
        logger.error(f"Dataset CSV not found: {csv_path}")
        sys.exit(1)

    dataset_dir = data_dir / args.dataset
    if not dataset_dir.exists():
        logger.error(f"Dataset directory does not exist: {dataset_dir}")
        sys.exit(1)

    results_dataset_dir = results_dir / args.dataset
    if not results_dataset_dir.exists():
        logger.warning(f"Results directory does not exist: {results_dataset_dir}")
        logger.warning("Evaluation will skip all complexes without predicted poses.")

    # Set default output path
    output_csv = args.output_csv
    if output_csv is None:
        output_csv = results_dir / f"{args.dataset}_evaluation.csv"

    # Run evaluation
    evaluate_dataset(
        dataset_name=args.dataset,
        data_dir=data_dir,
        results_dir=results_dir,
        top_n=args.top_n,
        run_pb=not args.no_pb_valid,  # PB validation enabled by default, disable with --no_pb_valid
        output_csv=output_csv
    )

    logger.info("Evaluation complete.")


if __name__ == "__main__":
    main()