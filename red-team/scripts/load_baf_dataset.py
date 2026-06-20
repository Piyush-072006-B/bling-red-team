import sys
import os
import json
import pandas as pd
import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import MinMaxScaler
from scipy.optimize import linear_sum_assignment

# Add red-team app to path so we can import seed_library
sys.path.insert(0, os.path.abspath('d:/bling-red-team/red-team'))
from app.engines.seed_library import get_all_seeds

DATA_FILE = "d:/bling-red-team/red-team/data/baf_base.csv"
OUTPUT_SEEDS = "d:/bling-red-team/red-team/data/computed_archetype_seeds.json"
OUTPUT_SIGS = "d:/bling-red-team/red-team/data/computed_archetype_signatures.json"

AMOUNT_TARGETS = {
    "digital_arrest": 850000,
    "structuring": 47000,
    "rapid_layering": 145000,
    "sim_swap": 450000,
    "account_takeover": 750000,
    "romance_scam": 250000,
    "pig_butchering": 900000,
    "merchant_terminal": 80000,
    "cash_in_mule": 300000,
    "otp_fraud": 400000,
    "investment_fraud": 500000,
    "cycle_round_trip": 85000,
    "salary_mule": 40000,
    "ghost_node_cash": 350000,
    "bipartite_mule": 150000,
    "low_slow_mule": 25000,
}

COUNTERPARTIES_OVERRIDES = {
    "digital_arrest": 2.0,
    "structuring": 2.0,
    "rapid_layering": 6.0,
    "sim_swap": 4.0,
    "account_takeover": 3.0,
    "romance_scam": 2.0,
    "pig_butchering": 3.0,
    "merchant_terminal": 45.0,
    "cash_in_mule": 15.0,
    "otp_fraud": 5.0,
    "investment_fraud": 8.0,
    "cycle_round_trip": 12.0,
    "salary_mule": 5.0,
    "ghost_node_cash": 10.0,
    "bipartite_mule": 25.0,
    "low_slow_mule": 4.0,
}

def main():
    print(f"Loading {DATA_FILE}...")
    df = pd.read_csv(DATA_FILE)
    
    # Filter for confirmed fraud
    df_fraud = df[df['fraud_bool'] == 1].copy()
    print(f"Loaded {len(df)} rows. Found {len(df_fraud)} confirmed fraud rows.")
    
    # Fill missing values with 0
    df_fraud.fillna(0, inplace=True)
    
    # 24 feature transformations
    bt_features = pd.DataFrame(index=df_fraud.index)
    scaler = MinMaxScaler()
    
    def normalize_01(series):
        return scaler.fit_transform(series.values.reshape(-1, 1)).flatten()
    
    # velocity_6h → burst_score → normalize 0-1
    bt_features['burst_score'] = normalize_01(df_fraud['velocity_6h'])
    
    # velocity_24h → velocity_ratio → normalize 0-1
    bt_features['velocity_ratio'] = normalize_01(df_fraud['velocity_24h'])
    
    # velocity_4w → temporal_acceleration → normalize 0-1
    bt_features['temporal_acceleration'] = normalize_01(df_fraud['velocity_4w'])
    
    # zip_count_4w → distinct_counterparties_30d → scale 1 to 50
    zc = df_fraud['zip_count_4w']
    bt_features['distinct_counterparties_30d'] = MinMaxScaler(feature_range=(1, 50)).fit_transform(zc.values.reshape(-1, 1)).flatten()
    
    # credit_risk_score → amount_zscore → normalize using z-score then clip to 0-5
    crs = df_fraud['credit_risk_score']
    zscore = (crs - crs.mean()) / (crs.std() + 1e-9)
    bt_features['amount_zscore'] = zscore.clip(0, 5)
    
    # session_length_in_minutes → hour_deviation → normalize 0-1
    bt_features['hour_deviation'] = normalize_01(df_fraud['session_length_in_minutes'])
    
    # device_distinct_emails_8w → counterparty_novelty → normalize 0-1
    bt_features['counterparty_novelty'] = normalize_01(df_fraud['device_distinct_emails_8w'])
    
    # bank_months_count → account_age_days → multiply by 30
    bt_features['account_age_days'] = df_fraud['bank_months_count'] * 30
    
    # prev_address_months_count → dormancy_break → multiply by 30, cap at 365
    bt_features['dormancy_break'] = (df_fraud['prev_address_months_count'] * 30).clip(0, 365)
    
    # current_address_months_count → txn_count_90d → use as proxy, scale to 0-200
    camc = df_fraud['current_address_months_count']
    bt_features['txn_count_90d'] = normalize_01(camc) * 200
    
    # days_since_request → payee_vpa_age_days → direct copy, clip to 0-365
    bt_features['payee_vpa_age_days'] = df_fraud['days_since_request'].clip(0, 365)
    
    # proposed_credit_limit → avg_txn_amount_30d → direct copy
    bt_features['avg_txn_amount_30d'] = df_fraud['proposed_credit_limit']
    
    # phone_mobile_valid + phone_home_valid + has_other_cards → kyc_completeness_score (avg)
    bt_features['kyc_completeness_score'] = (df_fraud['phone_mobile_valid'] + df_fraud['phone_home_valid'] + df_fraud['has_other_cards']) / 3.0
    
    # foreign_request → geography_switch → direct copy
    bt_features['geography_switch'] = df_fraud['foreign_request']
    
    # device_fraud_count → community_fraud_ratio → normalize 0-1, cap at 1.0
    bt_features['community_fraud_ratio'] = np.clip(normalize_01(df_fraud['device_fraud_count']), 0, 1.0)
    
    # keep_alive_session → channel_switch → invert
    bt_features['channel_switch'] = 1 - df_fraud['keep_alive_session']
    
    # income → txn_amount → scale by 50000 to approximate INR
    bt_features['txn_amount'] = df_fraud['income'] * 50000
    
    print(f"Computed {bt_features.shape[1]} tabular features.")
    
    # Print raw zip_count_4w cluster means before clustering to confirm variance
    print("Raw zip_count_4w stats:\n", df_fraud['zip_count_4w'].describe())
    
    # Step 3: KMeans
    print("Running KMeans with n_clusters=16...")
    kmeans = KMeans(n_clusters=16, random_state=42, n_init=10)
    bt_features['cluster'] = kmeans.fit_predict(bt_features)
    
    centroids = bt_features.groupby('cluster').mean()
    
    # We will map each cluster to an archetype based on rules.
    archetypes = [
        "rapid_layering", "digital_arrest", "structuring", "low_slow_mule",
        "account_takeover", "sim_swap", "romance_scam", "pig_butchering",
        "merchant_terminal", "cash_in_mule", "otp_fraud", "investment_fraud",
        "cycle_round_trip", "salary_mule", "ghost_node_cash", "bipartite_mule"
    ]
    
    cost_matrix = np.zeros((16, 16))
    for i in range(16):
        c = centroids.iloc[i]
        for j, arch in enumerate(archetypes):
            score = 0
            if arch == "rapid_layering":
                score = c['velocity_ratio'] + c['burst_score']
            elif arch == "digital_arrest":
                score = c['amount_zscore'] - c['kyc_completeness_score']
            elif arch == "structuring":
                score = c['txn_count_90d'] / 200.0 - c['txn_amount'] / 50000.0
            elif arch == "low_slow_mule":
                score = c['counterparty_novelty'] + c['dormancy_break'] / 365.0
            elif arch == "account_takeover":
                score = c['geography_switch'] + c['channel_switch']
            elif arch == "sim_swap":
                score = c['counterparty_novelty'] - c['account_age_days'] / 1000.0
            elif arch == "romance_scam":
                score = c['payee_vpa_age_days'] / 365.0 + c['avg_txn_amount_30d'] / 10000.0
            elif arch == "pig_butchering":
                score = c['txn_amount'] / 100000.0 + c['velocity_ratio']
            elif arch == "merchant_terminal":
                score = c['distinct_counterparties_30d'] / 50.0 + c['channel_switch']
            elif arch == "cash_in_mule":
                score = c['burst_score'] + c['geography_switch']
            elif arch == "otp_fraud":
                score = c['temporal_acceleration'] + c['channel_switch']
            elif arch == "investment_fraud":
                score = c['avg_txn_amount_30d'] / 10000.0 + c['community_fraud_ratio']
            elif arch == "cycle_round_trip":
                score = c['burst_score'] + c['distinct_counterparties_30d'] / 50.0
            elif arch == "salary_mule":
                score = c['txn_count_90d'] / 200.0 + c['kyc_completeness_score']
            elif arch == "ghost_node_cash":
                score = c['dormancy_break'] / 365.0 + c['geography_switch']
            elif arch == "bipartite_mule":
                score = c['distinct_counterparties_30d'] / 50.0 + c['community_fraud_ratio']
            
            # Maximize score => minimize negative score
            cost_matrix[i, j] = -float(score)
            
    row_ind, col_ind = linear_sum_assignment(cost_matrix)
    cluster_to_arch = {i: archetypes[j] for i, j in zip(row_ind, col_ind)}
    
    # Compute raw zip_count_4w means per cluster
    raw_zip_means = df_fraud.groupby(bt_features['cluster'])['zip_count_4w'].mean()
    
    # Fill in missing graph features using base seeds
    base_seeds = get_all_seeds()
    new_seeds = {}
    signatures = {}
    
    global_means = centroids.mean()
    global_stds = centroids.std()
    
    summary = []
    
    # Store requested debug prints
    debug_raw_zip = {}
    
    for i, arch in cluster_to_arch.items():
        c = centroids.iloc[i]
        
        if arch in ["digital_arrest", "structuring", "rapid_layering"]:
            debug_raw_zip[arch] = raw_zip_means.iloc[i]
        
        # Merge with existing graph features
        final_vector = base_seeds[arch].copy()
        for feature in centroids.columns:
            final_vector[feature] = float(c[feature])
            
        # OVERRIDE: distinct_counterparties_30d
        final_vector['distinct_counterparties_30d'] = COUNTERPARTIES_OVERRIDES.get(arch, 5.0)
        
        # OVERRIDE: avg_txn_amount_30d using fixed target lookup table
        fixed_amount = AMOUNT_TARGETS.get(arch, 100000)
        final_vector['avg_txn_amount_30d'] = float(fixed_amount)
        
        # Consistent amounts and volumes
        final_vector['txn_amount'] = float(fixed_amount)
        final_vector['txn_amount_log'] = np.log(fixed_amount) if fixed_amount > 0 else 0.0
        final_vector['txn_volume_last_1h'] = float(fixed_amount * final_vector['txn_count_last_1h'])
        final_vector['txn_volume_last_24h'] = float(fixed_amount * final_vector['txn_count_last_24h'])
        
        # Consistent thresholds
        final_vector['amount_vs_threshold_50000'] = 1.0 if fixed_amount >= 50000 else fixed_amount / 50000.0
        final_vector['amount_vs_threshold_100000'] = 1.0 if fixed_amount >= 100000 else fixed_amount / 100000.0
        final_vector['amount_vs_threshold_1000000'] = 1.0 if fixed_amount >= 1000000 else fixed_amount / 1000000.0
        
        new_seeds[arch] = final_vector
        
        # Most distinguishing: highest absolute Z-score compared to other clusters
        z_scores = ((c - global_means) / (global_stds + 1e-9)).abs()
        top_features = z_scores.sort_values(ascending=False).head(4).index.tolist()
        signatures[arch] = {f: 1.0 for f in top_features}
        
        count = (bt_features['cluster'] == i).sum()
        summary.append((arch, ", ".join(top_features), count))
        
    os.makedirs(os.path.dirname(OUTPUT_SEEDS), exist_ok=True)
    
    with open(OUTPUT_SEEDS, "w") as f:
        json.dump(new_seeds, f, indent=2)
        
    with open(OUTPUT_SIGS, "w") as f:
        json.dump(signatures, f, indent=2)
        
    print("\nSummary Table:")
    print(f"{'Archetype':<25} | {'Top Distinguishing Features':<80} | {'Sample Count'}")
    print("-" * 130)
    for arch, feats, count in summary:
        print(f"{arch:<25} | {feats:<80} | {count}")
        
    print("\nRAW zip_count_4w cluster means for review:")
    for arch in ["digital_arrest", "structuring", "rapid_layering"]:
        print(f"{arch}: {debug_raw_zip.get(arch, 0):.2f}")
        
    print(f"\nSaved {OUTPUT_SEEDS}")
    print(f"Saved {OUTPUT_SIGS}")

if __name__ == "__main__":
    main()
