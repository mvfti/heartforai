# Synthetic Insurance Database

## Overview
This directory contains a synthetic database of 1000 insurance policy holders for a Belgian insurance company (based on Belfius Home Insurance product).

## Files

### Data Files
- `.database/db.json` - JSON database containing 1000 synthetic policy holder records

### Python Modules
- `models.py` - SQLModel data models for policy holders
- `data_generator.py` - Mimesis-based synthetic data generator

## Data Model

Each policy holder record contains:

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `policy_id` | string | 9-digit policy identifier | "900100000" |
| `product_id` | string | 4-digit product identifier | "2178" |
| `product_name` | string | Name of insurance product | "Home Insurance - Base" |
| `coverage_desc` | string | Comma-separated coverage types | "Fire, Water Damage, Storm" |
| `policy_start_dt` | date | Policy start date (YYYY-MM-DD) | "2025-01-01" |
| `policy_end_dt` | date | Policy end date (YYYY-MM-DD) | "2026-01-01" |
| `premium_amt` | float | Premium amount in EUR | 450.00 |
| `language` | string | Language preference (NL/FR/EN) | "NL" |
| `postal_code` | string | 4-digit Belgian postal code | "2000" |

## Business Rules Implemented

### Regional Distribution
- **40% Flanders** (NL language)
  - Postal codes: 1500-1999, 2200-2999, 3000-3999, 8000-9999
- **40% Wallonia** (FR language)
  - Postal codes: 1300-1499, 4000-7999
- **20% Brussels** (NL or FR language)
  - Postal codes: 1000-1299

### Language Rules
- Flanders postal codes → NL language
- Wallonia postal codes → FR language
- Brussels postal codes → NL or FR (random)

### Date Rules
- Policy end date is at least 1 year after start date
- Policies can be 1, 2, or 3 years duration

## Insurance Products

The database includes 6 different insurance products based on Belfius offerings:

### Home Insurance
1. **Home Insurance - Base** (2178)
   - Coverage: Fire, Water Damage, Storm, Natural Disasters
   - Base premium: €350

2. **Home Insurance - Theft** (2179)
   - Coverage: Fire, Water Damage, Storm, Theft, Vandalism
   - Base premium: €520

3. **Home Insurance - Complete** (2180)
   - Coverage: Fire, Water Damage, Storm, Theft, Glass Breakage, Natural Disasters
   - Base premium: €680

4. **Home Insurance - Premium** (2181)
   - Coverage: Fire, Water Damage, Storm, Theft, Glass Breakage, Natural Disasters, Legal Protection
   - Base premium: €850

### Tenant Insurance
5. **Tenant Insurance - Basic** (2182)
   - Coverage: Fire, Water Damage, Civil Liability
   - Base premium: €180

6. **Tenant Insurance - Plus** (2183)
   - Coverage: Fire, Water Damage, Theft, Civil Liability
   - Base premium: €280

## Data Statistics

### Generated Dataset (1000 records)

**Language Distribution:**
- NL: ~52%
- FR: ~48%

**Product Distribution:**
- Each product: ~15-18% (evenly distributed)

**Premium Range:**
- Minimum: ~€144
- Maximum: ~€1,018
- Average: ~€470

## Usage

### Regenerate Data

To regenerate the synthetic database:

```bash
python data_generator.py
```

This will create/overwrite `.database/db.json` with 1000 new synthetic records.

### Load Data in Python

```python
import json

with open('.database/db.json', 'r') as f:
    policies = json.load(f)

# Access first policy
print(policies[0])
```

### Use with SQLModel

```python
from models import PolicyHolder
import json

with open('.database/db.json', 'r') as f:
    data = json.load(f)

# Convert to PolicyHolder objects
policies = [PolicyHolder(**record) for record in data]
```

## Dependencies

- `sqlmodel>=0.0.22` - Data modeling
- `mimesis>=19.1.0` - Synthetic data generation

Install with:
```bash
uv pip install sqlmodel mimesis
```

## Notes

- All data is synthetic and for development/testing purposes only
- No real customer information is included
- Policy IDs are randomly generated with prefix "900"
- Premiums include ±20% random variation from base amounts
- Data is seeded for reproducibility (seed=42)
