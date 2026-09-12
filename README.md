# SYNTAX - Security Orchestration & Analysis Platform

A comprehensive cybersecurity analysis platform providing threat intelligence, behavioral analytics, and security posture management capabilities.

---

## Overview

SYNTAX is a Python-based security operations tool designed to provide centralized visibility into enterprise security posture. It aggregates threat intelligence, analyzes user behavior patterns, monitors cloud infrastructure, and implements modern cryptographic standards.

## Core Components

### 1. Threat Intelligence Engine
Aggregates and correlates indicators of compromise (IOCs) from multiple threat intelligence feeds, providing actionable security insights with confidence scoring and automatic deduplication.

### 2. User & Entity Behavior Analytics (UEBA)
Monitors user activities and system behaviors to identify anomalies that may indicate insider threats, compromised accounts, or policy violations.

### 3. Cloud Security Posture Management (CSPM)
Scans cloud infrastructure across AWS, Azure, and GCP to identify misconfigurations, compliance gaps, and security risks.

### 4. Cryptographic Services
Implements post-quantum cryptographic algorithms for future-proof security communications.

### 5. Sanctions Evasion Tracker & Wartime Monetary Ethnography
Scores sanctions-evasion cases from typology-weighted indicators, classifies the
monetary regime of wartime field sites, and gates defensive sinkhole action on
military-alliance standing. See [Sanctions module](#sanctions-module) below.

### 6. IRS / BSA Filing Cypher Diagnostician
Decodes the coded fields on IRS- and FinCEN-administered financial reports, runs
consistency and threshold diagnostics over them, and emits evasion signals into
the sanctions tracker. See [Filings module](#filings-module) below.

### 7. World Bank Interim Audit System
Fiduciary review of Interim Unaudited Financial Reports on Bank-financed
projects, with Designated Account reconciliation, procurement threshold checks,
and debarment screening. See [Audit module](#audit-module) below.

---

## Installation

### Prerequisites
- Python 3.8 or higher
- pip package manager

### Setup

```bash
# Clone the repository
git clone https://github.com/naqqibb/Syntax.git
cd Syntax

# Install dependencies
pip install -r requirements.txt

# Run the platform
python syntax.py
```

---

## Usage

### Basic Execution

Run the platform to generate a comprehensive security assessment:

```bash
python syntax.py
```

This generates a detailed report including:
- Executive threat summary
- Behavioral analytics findings
- Threat intelligence correlations
- Cloud security assessment
- Compliance status
- API endpoint information

### Output

The platform outputs results directly to the terminal in a structured format suitable for security operations centers (SOCs) and security teams.

---

## Architecture

```
SYNTAX Platform
├── Threat Intelligence Module
│   ├── IOC Collection
│   ├── Threat Correlation
│   └── Confidence Scoring
├── UEBA Engine
│   ├── Behavior Monitoring
│   ├── Anomaly Detection
│   └── Risk Scoring
├── CSPM Scanner
│   ├── AWS Security Checks
│   ├── Azure Compliance
│   └── GCP Assessment
└── Cryptographic Layer
    └── Quantum-Safe Implementation
```

---

## Features

### Threat Intelligence
- Multi-source IOC aggregation
- Automatic deduplication
- Threat correlation engine
- Confidence-based scoring
- Real-time threat updates

### Behavioral Analytics
- User activity monitoring
- Anomaly detection algorithms
- Risk-based scoring
- Insider threat identification
- Entity behavior profiling

### Cloud Security
- Multi-cloud support (AWS, Azure, GCP)
- Configuration scanning
- Compliance framework mapping
- Misconfiguration detection
- Remediation guidance

### Security Standards
- ISO 27001 compliance checking
- PCI-DSS validation
- SOC 2 control mapping
- NIST framework alignment

---

## API Endpoints

The platform exposes the following REST API endpoints:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/mobile/login` | POST | Authentication endpoint |
| `/api/mobile/threats` | GET | Real-time threat feed |
| `/api/mobile/incidents` | GET | Incident dashboard |
| `/api/mobile/respond` | POST | Incident response actions |
| `/api/mobile/push-register` | POST | Push notification registration |
| `/api/mobile/analytics` | GET | Analytics data |

---

## Configuration

The platform can be configured through environment variables or configuration files. Key configuration areas include:

- Threat intelligence source URLs
- Cloud provider credentials
- UEBA detection thresholds
- Alert notification settings
- API rate limiting

---

## Use Cases

- **Security Operations Centers**: Centralized threat monitoring and response
- **Compliance Teams**: Automated compliance checking and reporting
- **Cloud Security**: Multi-cloud security posture management
- **Incident Response**: Real-time threat detection and analysis
- **Risk Management**: Behavioral risk assessment and scoring

---

## Sanctions Module

`SANCTIONS` is a pure-stdlib analyst control plane for tracking sanctions-evasion
networks in wartime economies and recording whether defensive sinkhole action
against their infrastructure is authorized. It records decisions; it performs no
network actions of its own. All data shipped with the module is synthetic.

```bash
python3 SANCTIONS           # terminal report
python3 SANCTIONS --json    # machine-readable report
```

### 1. Evasion tracking

An `EvasionCase` aggregates `EvasionSignal` observations, each attributed to one
of ten typologies (dual-use re-export, front procurement networks, dark-fleet AIS
gaps, correspondent-bank nesting, shell layering, trade misinvoicing, virtual-asset
chain-hopping, bullion flight, hawala settlement, parallel-FX arbitrage).

Scoring is deliberately corroboration-driven: contributions decay geometrically, so
one loud indicator cannot carry a case, while breadth of typology and independent
sourcing push the composite up. Cases tier as `ACUTE` / `ELEVATED` / `EMERGENT` /
`WATCH` / `NOISE`, and only the top two tiers are actionable.

### 2. Monetary ethnography

A `MonetaryObservation` records a field site with both registers: quantitative
indicators (parallel-market premium, dollarization, barter share, virtual-asset
settlement share, remittance dependency, scrip issuance) and the observed practices
that give them meaning. It yields a `MonetaryRegime` classification, a 0-100 stress
index, a narrative field note, and typology priors — the evasion routes that regime
structurally subsidizes.

| Regime | Typology priors |
| --- | --- |
| Stable fiat | Correspondent-bank nesting |
| Soft / hard dollarization | Trade misinvoicing, shell layering, bank nesting |
| Parallel market dominant | Parallel-FX arbitrage, misinvoicing, hawala |
| Virtual-asset substitution | Mixer/chain-hop laundering, shell layering |
| Scrip and coupon | Hawala settlement, bullion flight |
| Barter reversion | Bullion flight, hawala, dark-fleet transfers |

Priors only corroborate a case when the field site sits in a jurisdiction the case
actually touches, so an unrelated observation cannot inflate a score.

### 3. Alliance-gated sinkhole authority

`SinkholeAuthority` evaluates a request in a fixed precedence — evidentiary
sufficiency, then humanitarian exposure, then jurisdiction:

1. Cases below `ELEVATED` are `HELD_INSUFFICIENT_EVIDENCE`.
2. Civilian payment exposure above 15% without a cleared humanitarian review is
   `DENIED_HUMANITARIAN`, even in a friendly jurisdiction — remittance and
   medical-supply rails are a welfare question before an enforcement one.
3. Hosting jurisdiction is resolved against the requesting alliance (NATO, CSTO,
   SCO, AUKUS, EU CSDP, GCC, or non-aligned):

| Standing | Outcome |
| --- | --- |
| `MEMBER` | `AUTHORIZED`, conditioned on a domestic legal order |
| `PARTNER` | `AUTHORIZED_WITH_COALITION_CONCURRENCE` |
| `NEUTRAL` | `REFERRED_TO_LEGAL_PROCESS` (mutual legal assistance) |
| `CONTESTED` / `ADVERSARIAL` | `DENIED_JURISDICTION`, or referred to legal process when the registrar sits in a member or partner state |

Dual bloc membership resolves to the most restrictive standing, so a jurisdiction
cannot be laundered into an easier lane. No configuration produces unilateral
technical action inside a contested or adversarial state.

---

## Filings Module

`FILINGS` decodes the coded fields — the "cyphers" — carried by IRS- and
FinCEN-administered financial reports, runs diagnostics over them, and converts
surviving findings into evasion signals the [sanctions tracker](#sanctions-module)
can score.

```bash
python3 FILINGS             # diagnosis of the bundled synthetic filings
python3 FILINGS --codes     # print the cypher code tables
python3 FILINGS --json      # machine-readable diagnosis
```

> **Code tables are a structural model, not an authoritative transcription.**
> Thresholds, category codes, and filing deadlines change. Validate
> `CYPHER_TABLES` and `REPORTING_THRESHOLDS` against the current IRS and FinCEN
> instructions before operational use. The module reports where a filing looks
> internally inconsistent; it does not determine that any filing is wrong, and it
> makes no finding about any person. Bundled filings are synthetic.

### Instruments covered

| Instrument | Coded fields modelled |
| --- | --- |
| Form 8300 — cash over $10,000 | `method_of_payment`, `transaction_nature` |
| FinCEN 114 (FBAR) | `account_type`, `filer_capacity` |
| FinCEN 112 (CTR) | `transaction_type`, `conductor_role` |
| FinCEN 111 (SAR) | `activity_category`, `instrument_involved` |
| Form 8938 (FATCA) | `asset_category` |
| Form 926 | `transfer_category` |

### Diagnostic checks

| Finding | Severity | Condition |
| --- | --- | --- |
| `THRESHOLD_SPLIT` | Critical | Two or more sub-threshold filings by one subject, same instrument, aggregating past the threshold inside a 14-day window |
| `STRUCTURING_PROXIMITY` | High | A single amount landing in the 85–100% band below a threshold |
| `MISSING_REQUIRED_CYPHER` | High | A coded field the instrument requires is absent |
| `LATE_FILING` | High / Medium | Filed past the statutory window; escalates beyond 30 days overdue |
| `UNKNOWN_CYPHER` | Medium | A code absent from the field's table, or a field with no table |
| `CYPHER_AMOUNT_MISMATCH` | Medium | A coded instrument that disagrees with the coded activity |
| `JURISDICTION_CONFLICT` | Medium | Account jurisdiction diverging from the subject of record |
| `SUBTHRESHOLD_FILING` | Info | Below threshold — filed voluntarily or under another trigger |

The split check reports the **widest** qualifying run rather than the first pair
it finds, so a three-way split is not understated as a two-way one.

### Bridge into the sanctions tracker

Findings carrying a typology hint become `EvasionSignal` objects with
`irs-filing:<id>` provenance, at deliberately modest confidence — a filing
inconsistency is one thread, not a case. SAR instrument codes map directly:
`CVC` → virtual-asset chain-hopping, `BULL` → bullion flight, `TRADE` → trade
misinvoicing, `WIRE` → correspondent-bank nesting.

```python
diagnosis = build_demo_diagnosis()
for signal in diagnosis.to_sanctions_signals():
    case.add_signal(signal)
```

Because `EvasionCase` scoring decays repeated contributions, a stack of filing
findings alone will not carry a case into an actionable tier without independent
corroboration from another collection stream.

---

## Audit Module

`AUDIT` performs the fiduciary review of **Interim Unaudited Financial Reports
(IFRs)** submitted by borrowers on Bank-financed projects, together with the
procurement and counterparty checks that sit alongside them. Findings roll into
a financial-management risk rating and, where a fiduciary condition also reads as
evasion, cross into the [sanctions tracker](#sanctions-module).

```bash
python3 AUDIT               # audit of the bundled synthetic project
python3 AUDIT --json        # machine-readable audit
```

> **Thresholds and tolerances are a structural model, not an authoritative
> transcription** of any Financing Agreement or Bank procedure. Project-specific
> covenants govern — validate `AUDIT_PARAMETERS` and each project's category
> table against the applicable legal agreement before operational use. The system
> reports where a report looks internally inconsistent or covenant-divergent; it
> does not determine that any borrower, supplier, or person has done anything
> wrong. Bundled project data is synthetic.

### Checks

| Finding | Severity | Condition |
| --- | --- | --- |
| `DEBARRED_COUNTERPARTY` | Critical | Award to a counterparty active on the debarment or cross-debarment register at signature date |
| `CONTRACT_SPLITTING` | Critical | Sub-threshold awards to one supplier under one category aggregating past the prior-review threshold inside 90 days |
| `DA_UNRECONCILED` | Critical | Opening + advances − uses ≠ closing balance |
| `INELIGIBLE_EXPENDITURE` | Critical | Spend charged to a category the agreement makes ineligible |
| `CATEGORY_OVERRUN` | High | Cumulative spend past the category allocation |
| `UNDISCLOSED_CATEGORY` | High | Spend charged outside the agreed categories |
| `PRIOR_REVIEW_BYPASS` | High / Medium | At or above threshold with no prior review; Medium where limited competition sits just under it |
| `MODIFIED_AUDIT_OPINION` | Critical / High | Adverse or disclaimer; qualified |
| `LATE_IFR_SUBMISSION` | High / Medium | Past the 45-day covenant; escalates beyond 30 days overdue |
| `FINANCING_PERCENTAGE_BREACH` | Medium | Claimed above the category's agreed financing percentage |
| `SOE_CEILING_EXCEEDED` | Medium | SOE-supported spend above the ceiling ratio |
| `FORECAST_VARIANCE_BREACH` | Low | Actual diverging from forecast beyond tolerance |

Cumulative checks carry prior-period spend, so they run once per project rather
than once per report. Ineligible spend is reported once — re-reporting it as an
allocation overrun would double-count the same dollars.

### Risk rating

Any single critical finding carries a project to **High**. Below that the rating
escalates on volume, since a scatter of medium findings is itself a control-
environment signal: three highs → High, one high or three mediums → Substantial,
one medium or three lows → Moderate, otherwise Low.

### Debarment matching

`DebarmentRegistry` normalizes punctuation and entity suffixes (`Ltd`, `LLC`,
`FZE`, `GmbH`, …) before comparing, and checks the award date against the
debarment period so a contract signed before listing is not flagged. Matching is
deliberately conservative and exact-after-normalization: **a hit is a prompt to
verify against the published register, never a determination.**

### Bridge into the sanctions tracker

Debarment → front procurement network (0.65), contract splitting → shell layering
(0.55), prior-review bypass → front procurement network (0.45), ineligible and
undisclosed spend → trade misinvoicing (0.40). Signals carry
`wb-audit:<project>:<ref>` provenance.

---

## Development

### Project Structure

```
Syntax/
├── syntax.py           # Main application
├── requirements.txt    # Python dependencies
├── LICENSE            # Apache 2.0 license
├── README.md          # This file
├── OPERATOR           # Operator documentation
├── SYSTEM             # Operator system integration layer
├── SANCTIONS          # Sanctions evasion tracker & monetary ethnography
├── FILINGS            # IRS / BSA filing cypher diagnostician
├── AUDIT              # World Bank interim audit system
└── tests/             # Unit tests (python3 -m unittest discover -s tests)
```

### Dependencies

- `cryptography` - Cryptographic operations and post-quantum algorithms

### Contributing

Contributions are welcome. Please follow these guidelines:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/new-capability`)
3. Commit your changes (`git commit -am 'Add new capability'`)
4. Push to the branch (`git push origin feature/new-capability`)
5. Create a Pull Request

---

## Security Considerations

- This tool aggregates security data and should be deployed in a secure environment
- Ensure proper access controls are in place for API endpoints
- Review and validate all threat intelligence sources
- Regularly update dependencies for security patches
- Use strong authentication for cloud provider credentials

---

## License

Licensed under the Apache License, Version 2.0. See the [LICENSE](LICENSE) file for full details.

```
Copyright 2024 SYNTAX Security Platform

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
```

---

## Support

For issues, questions, or contributions:
- **GitHub Issues**: [Report bugs or request features](https://github.com/naqqibb/Syntax/issues)
- **Documentation**: Check the OPERATOR file for detailed usage information

---

## Roadmap

Future enhancements planned for SYNTAX:

- Extended threat intelligence source integrations
- Machine learning-based anomaly detection
- Advanced visualization dashboard
- Automated remediation capabilities
- Integration with SIEM platforms
- Container security scanning
- Network traffic analysis

---

## Disclaimer

This tool is provided for legitimate security operations and research purposes. Users are responsible for ensuring compliance with applicable laws and regulations in their jurisdiction. The authors assume no liability for misuse of this software.

---

**Version**: 18.0  
**Status**: Active Development  
**Last Updated**: January 2025
