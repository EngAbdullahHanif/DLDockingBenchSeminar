# CADD Seminar 26 - Data Architecture

This directory contains the molecular data used for Computer-Aided Drug Design (CADD) experiments and model training. The data is organized into several subdirectories and CSV files for different use cases.

## Directory Structure

```
data/
├── full_train/                    # Complete training dataset (to be published later)
├── full_test/                     # Complete testing dataset (to be published later)
├── proto_train/                   # Prototype training dataset (in ZIP)
├── proto_test/                    # Prototype testing dataset (in ZIP)
├── posebusters_filtered/          # High-quality filtered structures (to be published later)
├── full_train.csv                 # Training set metadata (to be published later)
├── full_test.csv                  # Test set metadata (to be published later)
├── proto_train.csv                # Prototype training metadata (in ZIP)
├── proto_test.csv                 # Prototype testing metadata (in ZIP)
├── posebusters_filtered.csv       # Filtered set metadata (to be published later)
└── prototype_model_data.zip       # Compressed prototype data
```


### Archive Contents (prototype_model_data.zip)
The ZIP file contains:
- **proto_train/**: 712 protein-ligand complexes for training
- **proto_test/**: 118 protein-ligand complexes for testing
- **proto_train.csv**: Metadata for prototype training set
- **proto_test.csv**: Metadata for prototype testing set

### To Be Published Later
- **full_train/** & **full_train.csv**: Complete training dataset (27,532 complexes)
- **full_test/** & **full_test.csv**: Complete testing dataset (4,743 complexes)
- **posebusters_filtered/** & **posebusters_filtered.csv**: High-quality filtered structures (308 complexes)

## Dataset Descriptions

### 1. Prototype Data (Published in ZIP)

- **Size**: 830 total complexes (712 training + 118 testing)
- **Purpose**: Rapid model development and prototyping
- **File Format**: Each complex consists of:
  - `*_ligand_refined.sdf`: Ligand structure in SDF format
  - `*_protein_refined.pdb`: Protein structure in PDB format

### 2. Full Training and Testing Sets (To Be Published Later)

- **full_train/**: Complete training dataset (27,532 complexes)
- **full_test/**: Complete testing dataset (4,743 complexes)
- **File Format**: Same as prototype data with refined structures

### 3. PoseBusters Filtered Set (To Be Published Later)

- **posebusters_filtered/**: High-quality dataset of 308 complexes
- **Filtering**: Structures passed PoseBusters quality filters
- **File Format**:
  - `*_ligand.sdf`: Ligand structures
  - `*_protein.pdb`: Protein structures
- **Naming Convention**: `{PDBID}_{LIGAND_NAME}_{type}.{ext}`
  - Example: `5SAK_ZRY_ligand.sdf`, `5SAK_ZRY_protein.pdb`


## CSV File Specifications

### Training/Testing CSV Files
All training and testing CSV files contain the following columns:

| Column | Description |
|--------|-------------|
| `ligand_file_name` | SDF filename of the ligand structure |
| `protein_file_name` | PDB filename of the protein structure |
| `Year` | Publication year of the crystal structure |
| `Log Binding Affinity` | Log-transformed binding affinity value |
| `Binding Affinity Measurement` | Type of measurement (ki, kd, ic50, etc.) |
| `PDBID` | Protein Data Bank identifier |

### PoseBusters Filtered CSV
The `posebusters_filtered.csv` file contains:

| Column | Description |
|--------|-------------|
| `ligand_name` | Short ligand identifier (e.g., ZRY, 1K2) |
| `ligand_file` | Full SDF filename |
| `protein_file` | Corresponding PDB filename |


## File Naming Conventions

### Full/Prototype Sets
Format: `{PDBID}_{LIGAND}_{CHAIN}_{RESIDUE}_TYPE_refined.{ext}`
- Example: ligand: `10gs_VWW_A_210_ligand_refined.sdf`, protein: `10gs_VWW_A_210_protein_refined.pdb` 


## Usage

1. **Prototype (ZIP)**: Use for rapid development and initial model training (First milestone)
2. **Full Dataset**: Use for comprehensive model training and evaluation (Final submission)
3. **PoseBusters Filtered**: Use for high-quality benchmark evaluations (Final submission / Optional for first milestone)
