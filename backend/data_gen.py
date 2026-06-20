import pandas as pd
import networkx as nx
from faker import Faker
import random
from datetime import datetime, timedelta
import numpy as np


# DATA GENERATOR 


fake = Faker('en_IN')
Faker.seed(42)
random.seed(42)

TOTAL_USERS = 300
TOTAL_EVENTS = 1200


# 1. IDENTITY SNAPSHOTS

users = []
departments = ["Engineering", "Finance", "Data", "Security", "HR", "IT"]

for i in range(1000, 1000 + TOTAL_USERS):
    emp_id = f"E{i}"
    name = fake.name()
    dept = random.choice(departments)
    manager = fake.name()
    
    is_oncall = random.random() < 0.15  # 15% On-call
    
    last_login = datetime.now() - timedelta(days=random.randint(1, 180), hours=random.randint(0, 23))
    
    users.append({
        "employee_id": emp_id,
        "display_name": name,
        "ad_username": f"{name.split()[0].lower()}.{name.split()[-1].lower()}@corp.in",
        "ad_status": "active",
        "aws_username": f"aws-user-{i}",
        "aws_status": "active",
        "okta_username": f"{name.split()[0].lower()}@company.in",
        "okta_status": "active",
        "manager": manager,
        "department": dept,
        "employment_status": "active",
        "termination_date": pd.NaT,  # NULL for active
        "last_login": last_login.isoformat(),
        "is_oncall": is_oncall
    })

users_df = pd.DataFrame(users)
all_ids = list(users_df["employee_id"])
random.shuffle(all_ids)

# Inject Anomalies (10% Orphans, 10% Over-priv, 5% Dormant, 3% Token Abuse)
orphan_ids = all_ids[:30]
overpriv_ids = all_ids[30:60]
dormant_ids = all_ids[60:75]
token_abuse_ids = all_ids[75:84]

# Apply Orphan states (Active in AWS/Okta, Terminated in HR)
users_df.loc[users_df["employee_id"].isin(orphan_ids), "employment_status"] = "terminated"
term_dates = [datetime.now() - timedelta(days=random.randint(10, 90)) for _ in orphan_ids]
mask = users_df["employee_id"].isin(orphan_ids)
users_df.loc[mask, "termination_date"] = pd.Series(pd.to_datetime(term_dates)).dt.floor("s").values

# Mark Overpriv as Contractors
users_df.loc[users_df["employee_id"].isin(overpriv_ids), "employment_status"] = "contractor"

# 2. OFFBOARDING RECORDS

offboarding_records = []
for emp in orphan_ids:
    term_date = users_df.loc[users_df["employee_id"] == emp, "termination_date"].values[0]

    if pd.isna(term_date):
        continue
    
    ad_delay = timedelta(days=random.randint(0, 3))
    ad_dis = (term_date + ad_delay).strftime('%Y-%m-%d')
    
    # 50% chance to leave AWS/Okta as NULL (Orphan)
    aws_dis = np.nan if random.random() < 0.5 else (term_date + timedelta(days=random.randint(4, 10))).strftime('%Y-%m-%d')
    okta_dis = np.nan if random.random() < 0.5 else (term_date + timedelta(days=random.randint(4, 10))).strftime('%Y-%m-%d')
    
    offboarding_records.append({
        "employee_id": emp,
        "hr_termination_date": pd.to_datetime(term_date).strftime("%Y-%m-%d"),
        "ad_disabled_date": ad_dis,
        "aws_disabled_date": aws_dis,
        "okta_disabled_date": okta_dis
    })

offboarding_df = pd.DataFrame(offboarding_records)


# 3. GROUP / ROLE MAPPINGS

G = nx.DiGraph()
groups = ["AD_Group_DevOps", "AD_Group_Nested_Billing", "AD_Group_Helpdesk", "AWS_Role_BillingAccess", "AWS_Role_AdminAccess", "Okta_Group_SuperAdmin"]
roles = ["AD_Domain_Admin", "AWS_S3_FullAccess", "Okta_App_Salesforce_Admin"]

mappings = []

def add_mapping(s_id, s_type, t_id, t_type, plat):
    G.add_edge(s_id, t_id, platform=plat)
    mappings.append({
        "source_id": s_id, "source_type": s_type,
        "target_id": t_id, "target_type": t_type,
        "platform": plat
    })

# System Nested Inheritance
add_mapping("AD_Group_Nested_Billing", "Group", "AD_Group_DevOps", "Group", "Internal")
add_mapping("AD_Group_DevOps", "Group", "AWS_Role_BillingAccess", "Role", "AD-to-AWS")
add_mapping("AD_Group_Helpdesk", "Group", "Okta_App_Salesforce_Admin", "Role", "AD-to-Okta")

# Assign Users
for emp in all_ids:
    add_mapping(emp, "Employee", random.choice(groups), "Group", "Mixed")

# Inject Overpriv
for emp in overpriv_ids:
    add_mapping(emp, "Employee", "AWS_Role_AdminAccess", "Role", "AWS")
    add_mapping(emp, "Employee", "Okta_Group_SuperAdmin", "Group", "Okta")

# Inject Dormant Admins
for emp in dormant_ids:
    add_mapping(emp, "Employee", "AD_Domain_Admin", "Role", "AD")

# Ensure On-Call users have AWS Admin
for emp in all_ids:
    if users_df.loc[users_df["employee_id"] == emp, "is_oncall"].iloc[0]:
        add_mapping(emp, "Employee", "AWS_Role_AdminAccess", "Role", "AWS")

mappings_df = pd.DataFrame(mappings)


# 4. AUDIT LOGS

events = []
normal_events = ["Login_Success", "Login_Failed", "API_Call", "Resource_Access"]
admin_events = ["Role_Assigned", "Role_Removed", "Group_Added", "Group_Removed", "Assumed_Admin_Role", "Privilege_Escalation", "Token_Used"]

# Normal
for _ in range(int(TOTAL_EVENTS * 0.80)):
    emp = random.choice(all_ids)
    events.append({
        "employee_id": emp,
        "platform": random.choice(["AD", "AWS", "Okta"]),
        "event": random.choice(normal_events),
        "timestamp": (datetime.now() - timedelta(days=random.randint(0, 30))).isoformat()
    })

# Privilege Escalation
for _ in range(int(TOTAL_EVENTS * 0.05)):
    events.append({
        "employee_id": random.choice(all_ids),
        "platform": random.choice(["AWS", "Okta"]),
        "event": random.choice(["Privilege_Escalation", "Assumed_Admin_Role"]),
        "timestamp": (datetime.now() - timedelta(days=random.randint(1, 10))).isoformat()
    })

# Token Abuse
for _ in range(int(TOTAL_EVENTS * 0.04)):
    events.append({
        "employee_id": random.choice(token_abuse_ids),
        "platform": "AWS",
        "event": "Token_Used",
        "timestamp": (datetime.now() - timedelta(days=random.randint(0, 5))).isoformat()
    })

# Admin/Role Changes
for _ in range(int(TOTAL_EVENTS * 0.11)):
    events.append({
        "employee_id": random.choice(all_ids),
        "platform": random.choice(["AD", "AWS", "Okta"]),
        "event": random.choice(admin_events[:4]),
        "timestamp": (datetime.now() - timedelta(days=random.randint(0, 60))).isoformat()
    })

events_df = pd.DataFrame(events)


# SAVE FILES

users_df.to_csv("./data/identities.csv", index=False)
offboarding_df.to_csv("./data/offboarding_records.csv", index=False)
mappings_df.to_csv("./data/group_mappings.csv", index=False)
events_df.to_csv("./data/audit_logs.csv", index=False)

print("Datasets generated.")