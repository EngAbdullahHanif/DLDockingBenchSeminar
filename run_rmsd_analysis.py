import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from rdkit import Chem
from rdkit.Chem import rdMolAlign

# Paths configuration
csv_path = "data/prototype_model_data/proto_test.csv"
src_dir = "data/prototype_model_data/proto_test"
pred_dir = "results/proto_test"

if not os.path.exists(csv_path):
    print("Error: CSV file not found. Please unzip the prototype dataset.")
    exit(1)

df = pd.read_csv(csv_path)
results = []

print(f"Analyzing {len(df)} entries from CSV...")
for idx, row in df.iterrows():
    lig_file = row['ligand_file_name']
    complex_id = lig_file.replace('_ligand_refined.sdf', '')
    
    ref_path = os.path.join(src_dir, lig_file)
    pred_path = os.path.join(pred_dir, f"{complex_id}_pred.sdf")
    
    if os.path.exists(ref_path) and os.path.exists(pred_path):
        ref_suppl = Chem.SDMolSupplier(ref_path, removeHs=False)
        pred_suppl = Chem.SDMolSupplier(pred_path, removeHs=False)
        
        ref_mol = ref_suppl[0] if ref_suppl else None
        pred_mol = pred_suppl[0] if pred_suppl else None
        
        if ref_mol is not None and pred_mol is not None:
            try:
                # Calculate symmetry-corrected heavy-atom RMSD
                rmsd = rdMolAlign.GetBestRMS(pred_mol, ref_mol)
                results.append({
                    'complex_id': complex_id,
                    'rmsd': rmsd
                })
            except Exception as e:
                print(f"Error aligning {complex_id}: {e}")

df_results = pd.DataFrame(results)
print(f"Successfully analyzed {len(df_results)}/{len(df)} complexes.")

if len(df_results) > 0:
    mean_rmsd = df_results['rmsd'].mean()
    median_rmsd = df_results['rmsd'].median()
    success_2a = (df_results['rmsd'] < 2.0).mean() * 100
    success_1a = (df_results['rmsd'] < 1.0).mean() * 100

    print("\n=== SUMMARY STATISTICS ===")
    print(f"Mean RMSD:                 {mean_rmsd:.4f} Å")
    print(f"Median RMSD:               {median_rmsd:.4f} Å")
    print(f"Success Rate (< 2.0 Å):     {success_2a:.2f}%")
    print(f"Success Rate (< 1.0 Å):     {success_1a:.2f}%")
    
    # Save statistics to CSV
    stats_csv = "results/proto_test_evaluation_summary.csv"
    df_results.to_csv(stats_csv, index=False)
    print(f"Detailed statistics saved to {stats_csv}")
    
    # Plotting the cumulative distribution
    sorted_rmsds = np.sort(df_results['rmsd'])
    yvals = np.arange(len(sorted_rmsds)) / float(len(sorted_rmsds)) * 100

    plt.figure(figsize=(7, 5), dpi=120)
    plt.plot(sorted_rmsds, yvals, label="KarmaDock", color="#1f77b4", linewidth=2.5)
    plt.axvline(x=2.0, color="#d62728", linestyle="--", alpha=0.8, label="Success threshold (2.0 Å)")
    plt.title("Cumulative Distribution of Top-1 RMSD (proto_test)", fontsize=13, pad=12)
    plt.xlabel("RMSD (Å)", fontsize=11)
    plt.ylabel("Percentage of Complexes (%)", fontsize=11)
    plt.xlim(0, 10)
    plt.ylim(0, 105)
    plt.grid(True, linestyle=":", alpha=0.6)
    plt.legend(loc="lower right", fontsize=10)
    plt.tight_layout()
    plot_path = "results/proto_test_rmsd_cdf.png"
    plt.savefig(plot_path)
    print(f"CDF Plot saved to {plot_path}")
else:
    print("No results analyzed.")
