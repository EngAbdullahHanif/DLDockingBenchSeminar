# Results Directory Guide

This directory contains predicted poses for evaluation against reference structures. The evaluation script expects specific naming conventions and file formats.

**Important**: All evaluation commands should be run from the repository root directory (CADDSeminar26/).

## Directory Structure

```
results/
├── proto_test/
│   ├── 3ix2_AC2_A_302_pred.sdf
│   ├── 4jdf_SPD_A_401_pred.sdf
│   └── ...
├── posebusters_filtered/
│   ├── 5SAK_ZRY_pred.sdf
│   ├── 5SB2_1K2_pred.sdf
│   └── ...
├── full_test/
│   ├── 3ix2_AC2_A_302_pred.sdf
│   ├── 5oai_B5K_A_201_pred.sdf
│   └── ...
└── README.md (this file)
```

## Naming Convention

### Predicted Pose Files

**Format**: `{complex_identifier}_pred.sdf`

The `complex_identifier` is derived from the reference ligand filename in each dataset's CSV file:

#### proto_test / full_test datasets:
- **Reference ligand**: `3ix2_AC2_A_302_ligand_refined.sdf`
- **Predicted poses**: `3ix2_AC2_A_302_pred.sdf`
- **Pattern**: Remove `_ligand_refined.sdf` suffix

#### posebusters_filtered dataset:
- **Reference ligand**: `5SAK_ZRY_ligand.sdf`
- **Predicted poses**: `5SAK_ZRY_pred.sdf`
- **Pattern**: Remove `_ligand.sdf` suffix

## File Format Requirements

### SDF Structure
- **Multi-conformer SDF**: Each file can contain multiple poses (conformers) for the same ligand
- **Ranking**: Poses should be ordered by confidence/score (best pose first)
- **Coordinates**: 3D coordinates required for RMSD calculation

## Dataset-Specific Examples

### proto_test Dataset
```bash
# CSV mapping (proto_test.csv)
ligand_file_name,protein_file_name,Year,Log Binding Affinity,Binding Affinity Measurement,PDBID
3ix2_AC2_A_302_ligand_refined.sdf,3ix2_AC2_A_302_protein_refined.pdb,2021,-4.900008766455316,kd,3ix2

# Expected predicted pose file
results/proto_test/3ix2_AC2_A_302_pred.sdf
```

### posebusters_filtered Dataset
```bash
# CSV mapping (posebusters_filtered.csv)
ligand_name,ligand_file,protein_file
ZRY,5SAK_ZRY_ligand.sdf,5SAK_ZRY_protein.pdb

# Expected predicted pose file
results/posebusters_filtered/5SAK_ZRY_pred.sdf
```

### full_test Dataset
```bash
# CSV mapping (full_test.csv)
ligand_file_name,protein_file_name,Year,Log Binding Affinity,Binding Affinity Measurement,PDBID
5oai_B5K_A_201_ligand_refined.sdf,5oai_B5K_A_201_protein_refined.pdb,2019,-7.0,ki,5oai

# Expected predicted pose file
results/full_test/5oai_B5K_A_201_pred.sdf
```

## Evaluation Usage

**Run all commands from the repository root directory:**

### Default Evaluation (RMSD + PoseBusters validation)
```bash
# Evaluate proto_test dataset, top-1 pose (default settings)
python evaluation/evaluation.py --dataset proto_test

# Evaluate multiple poses
python evaluation/evaluation.py --dataset proto_test --top_n 5
```

### RMSD Only (Skip PoseBusters validation)
```bash
# Skip physical validity checks for faster evaluation
python evaluation/evaluation.py --dataset proto_test --no_pb_valid
```

### Custom Output
```bash
# Specify custom output CSV location
python evaluation/evaluation.py --dataset full_test --output_csv results/my_evaluation.csv
```

## Evaluation Metrics

### RMSD Metrics
- **Symmetry-corrected RMSD**: Heavy-atom RMSD accounting for molecular symmetry
- **RMSD < 2.0 Å**: Success rate for poses with RMSD below 2.0 Angstroms
- **RMSD < 1.0 Å**: Success rate for high-quality poses

### PoseBusters Metrics (enabled by default)
- **PB-Valid**: Percentage of poses passing all physical validity checks
- **Individual checks**: Bond lengths, angles, clashes, strain energy, etc.

### Ranking Metrics
- **Top-1**: Performance of the best-ranked pose
- **Best-of-N**: Performance of the best pose among top-N predictions

## Troubleshooting

### File Validation
```bash
# Check if your SDF files are valid
python -c "from rdkit import Chem; print('Valid' if Chem.SDMolSupplier('your_file.sdf')[0] else 'Invalid')"

# Count poses in SDF
python -c "from rdkit import Chem; print(len([m for m in Chem.SDMolSupplier('your_file.sdf') if m]))"
```

## Quick Start

1. **Prepare your predictions**:
   - Place SDF files in appropriate dataset subdirectories
   - Follow naming convention: `{complex_identifier}_pred.sdf`
   - Ensure poses are ranked (best first)

2. **Run evaluation**:
   ```bash
   python evaluation/evaluation.py --dataset proto_test
   ```

3. **Check results**:
   - Results saved to `results/{dataset}_evaluation.csv`
   - Summary statistics printed to console

For more details, see the evaluation script documentation and help:
```bash
python evaluation/evaluation.py --help
```