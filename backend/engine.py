import pandas as pd
import networkx as nx
from datetime import datetime
import numpy as np

class IdentityRiskEngine:
    def __init__(self):
        self.graph = nx.DiGraph()
        
        # Load strictly schema-compliant data
        self.users_df = pd.read_csv("identities.csv")
        self.offboarding_df = pd.read_csv("offboarding_records.csv")
        self.events_df = pd.read_csv("audit_logs.csv")
        
        # Pre-process events
        self.events_df['timestamp'] = pd.to_datetime(self.events_df['timestamp'], errors='coerce')
        self.user_last_event = self.events_df.groupby('employee_id')['timestamp'].max().to_dict()
        
        self._build_graph()

    def _build_graph(self):
        mappings_df = pd.read_csv("group_mappings.csv")
        for _, row in mappings_df.iterrows():
            self.graph.add_node(row["source_id"], type=row["source_type"])
            self.graph.add_node(row["target_id"], type=row["target_type"])
            self.graph.add_edge(row["source_id"], row["target_id"], platform=row["platform"])

    def get_effective_privileges(self, user_id):
        """Multi-hop traversal returning ONLY Role nodes."""
        if user_id not in self.graph:
            return []
        
        reachable = set(nx.descendants(self.graph, user_id))
        roles = []
        for node in reachable:
            if self.graph.nodes[node].get('type') == 'Role':
                roles.append(node)
        return roles

    def calculate_risk_scores(self):
        results = []
        
        # Pre-calculate behavioral anomalies from audit logs
        token_abuse_events = self.events_df[self.events_df['event'] == 'Token_Used']['employee_id'].unique()
        escalation_events = self.events_df[self.events_df['event'].isin(['Privilege_Escalation', 'Assumed_Admin_Role'])]['employee_id'].unique()

        for _, user in self.users_df.iterrows():
            emp_id = user["employee_id"]
            privs = self.get_effective_privileges(emp_id)
            
            # Initialize Modular Risks
            orphan_risk = 0
            admin_risk = 0
            dormant_risk = 0
            token_risk = 0
            escalation_risk = 0
            graph_nesting_risk = 0
            
            risk_factors = []
            is_oncall = bool(user["is_oncall"])

            # --- TIME-BASED LOGIC ---
            last_event_date = self.user_last_event.get(emp_id)
            days_inactive = 999
            if pd.notna(last_event_date):
                days_inactive = (datetime.now() - last_event_date).days

            # --- 1. ORPHAN RISK ---
            offboard_record = self.offboarding_df[self.offboarding_df['employee_id'] == emp_id]
            if not offboard_record.empty:
                rec = offboard_record.iloc[0]
                if pd.isna(rec['aws_disabled_date']) or pd.isna(rec['okta_disabled_date']):
                    orphan_risk = 35
                    risk_factors.append("Orphaned Account: NULL cloud disable date in HR records")
                else:
                    # Check for delayed deprovisioning (>3 days gap)
                    term_date = pd.to_datetime(rec['hr_termination_date'])
                    aws_dis = pd.to_datetime(rec['aws_disabled_date'])
                    if (aws_dis - term_date).days > 3:
                        orphan_risk = 20
                        risk_factors.append("Delayed Deprovisioning: AWS disabled >3 days after termination")

            # --- 2. ADMIN RISK ---
            is_aws_admin = "AWS_Role_AdminAccess" in privs
            is_okta_admin = "Okta_App_Salesforce_Admin" in privs or "Okta_Group_SuperAdmin" in privs
            is_ad_admin = "AD_Domain_Admin" in privs
            
            admin_weight = (is_ad_admin * 85) + (is_aws_admin * 70) + (is_okta_admin * 60)
            if admin_weight > 0:
                admin_risk = min(30, int((admin_weight / 85) * 30))
                if sum([is_ad_admin, is_aws_admin, is_okta_admin]) >= 2:
                    admin_risk = 30
                    risk_factors.append("Cross-Platform Admin Risk")
                elif user["employment_status"] == "contractor":
                    risk_factors.append("Contractor with unilateral admin access")

            # --- 3. DORMANT RISK ---
            if (is_aws_admin or is_ad_admin) and days_inactive > 90:
                dormant_risk = 25
                risk_factors.append(f"Dormant Admin: No activity for {days_inactive} days")

            # --- 4. TOKEN RISK ---
            if emp_id in token_abuse_events:
                token_risk = 20
                risk_factors.append("Token Abuse: 'Token_Used' event detected in audit logs")

            # --- 5. ESCALATION RISK ---
            if emp_id in escalation_events:
                escalation_risk = 25
                risk_factors.append("Privilege Escalation: Anomalous admin assumption event detected")

            # --- 6. GRAPH NESTING RISK ---
            admin_roles = {"AWS_Role_AdminAccess", "Okta_Group_SuperAdmin", "AD_Domain_Admin"}
            for target in privs:
                if target in admin_roles:
                    try:
                        path = nx.shortest_path(self.graph, emp_id, target)
                        # If path is Employee -> Group -> Group -> Role (length 4)
                        if len(path) > 3:
                            graph_nesting_risk = 15
                            risk_factors.append(f"Hidden Nested Admin: Reached {target} via {len(path)-1} hops")
                            break
                    except nx.NetworkXNoPath:
                        continue

            # --- FINAL SCORING ---
            total_score = orphan_risk + admin_risk + dormant_risk + token_risk + escalation_risk + graph_nesting_risk
            
            # On-Call Mitigation
            if is_oncall and orphan_risk == 0:
                total_score = max(0, total_score - 40)
                risk_factors.append("Mitigation: User is On-Call (Score reduced)")

            total_score = min(total_score, 100)

            results.append({
                "employee_id": emp_id,
                "display_name": user["display_name"],
                "risk_score": total_score,
                "risk_factors": risk_factors if risk_factors else ["None"],
                "effective_privileges": privs
            })

        return sorted(results, key=lambda x: x["risk_score"], reverse=True)

    def summary(self):
        results = self.calculate_risk_scores()
        print("\n=== TOP 5 RISKY IDENTITIES ===")
        for r in results[:5]:
            print(f"\nName: {r['display_name']} ({r['employee_id']})")
            print(f"Score: {r['risk_score']}")
            print(f"Factors: {r['risk_factors']}")
            print(f"Privileges: {r['effective_privileges']}")

if __name__ == "__main__":
    engine = IdentityRiskEngine()
    engine.summary()