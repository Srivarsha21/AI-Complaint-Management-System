# Office and complaint-channel data sources (Module 8)

Data file: `backend/app/location/data/hyderabad_offices.json` (20 records), loaded with
`python -m app.scripts.load_offices` (idempotent upsert by name + organisation; rejects any record
without `source_url` / `verified_on`).

Every record was read from the official page below on **2026-10-10**. Anything a page did not state
(phone, email, PIN, hours, coordinates) is left `null`. All records are `source_type = official`.
No document requirements are stored, because none of the sources list them for these complaint types.

## Context: GHMC reorganisation (2026)

The GHMC, CMC and MMC home pages link the *Core Urban Region (Integrated Governance) Act, 2026*. Under it
the old GHMC area is split into three corporations: GHMC, Cyberabad Municipal Corporation (CMC) and
Malkajgiri Municipal Corporation (MMC). All three official websites link to the same Integrated Grievance
System (`igs.ghmc.gov.in`). Zone names in the notes are taken from each corporation's Key Contacts page.

## Sources

| Source URL | Organisation | What was taken |
|---|---|---|
| https://www.ghmc.gov.in/KeyContacts.aspx | GHMC | Head office address "CC Complex Tank Bund Road, Lower Tank Bund Hyderabad: 500063", phone 040-23225397, helpline "21111111" (printed without STD code), GHMC zone names |
| https://www.ghmc.gov.in/ | GHMC | IGS grievance link `https://igs.ghmc.gov.in/operator/send_otp_mobile`, status link `/operator/search`, app links (Google Play `cgg.gov.ghmc` "My CURE", App Store "MyGHMC Citizen") |
| https://cmc.telangana.gov.in/ and `/KeyContacts.aspx` | CMC | Official site; "Lodge Grievance" links to IGS; zones Serilingampally, Kukatpally, Quthbullapur |
| https://mmc.telangana.gov.in/ and `/KeyContacts.aspx` | MMC | Official site; "Lodge Grievance" links to IGS; zones Malkajgiri, Uppal, L.B. Nagar |
| https://www.hyderabadwater.gov.in/en/index.php/contact-us | HMWSSB | Head office address "Administrative Office Building, Khairatabad, Hyderabad - 4, Telangana", EPABX 040-23433933, mdhmwssb@hyderabadwater.gov.in, "Customer Care Center 155313" for water supply & sewerage complaints |
| https://www.hyderabadwater.gov.in/ | HMWSSB | "24 Hours Customer Care:155 313", customer-support@hyderabadwater.gov.in, "Register Grievances" page link, Google Maps embed of "HMWSSB Building" (17.410859, 78.4638293) |
| https://www.hyderabadwater.gov.in/en/index.php/services/customers-services/know-your-area-offices | HMWSSB | "Know Your Area Officer" lookup page (embeds bms.hyderabadwater.gov.in) |
| https://tgsouthernpower.org/ | TGSPDCL | Official name; "24x7 Toll-Free: 1912"; "No Power Complaint" link `https://webportal.tgsouthernpower.org/NPC/`; address "# 6-1-50, Mint Compound, Hyderabad - 500 063"; customerservice@tgsouthernpower.org; Google Maps embed (17.4082566, 78.4673308). The site is a single-page app, so these were read from its published JS bundle. |
| https://tgpcb.cgg.gov.in/ | TGPCB | Address "A-3, Paryavaran Bhavan, Sanath Nagar Rd, ... Hyderabad, Telangana 500018", "PBX Number : 040-23887500", "Toll Free Number : 10741", "Janavani Kalushyanivarini (Public Grievance)" link (hosted on telangana-ccr.glensserver.com), map embed centre (17.45702, 78.43902, approximate) |
| https://hydraa.telangana.gov.in/ | HYDRAA | Toll-free helpline 1070 for "civic emergencies, trees down, blockages, or active asset violations"; address "7th Floor, Buddha Bhavan, Rani Gunj, Secunderabad – 500003" |
| https://prajavani.cgg.gov.in/ | Government of Telangana | Prajavani grievance programme description, support.prajavani@cgg.gov.in |
| https://www.tspolice.gov.in/ | Telangana State Police | "EMERGENCY CONTACTS – Police: 112" |

## Coordinates

| Record | Coordinates source |
|---|---|
| GHMC Head Office | OpenStreetMap Nominatim (approximate): OSM townhall "Greater Hyderabad Municipal Corporation", PIN 500063 |
| HMWSSB Head Office | Google Maps embed on the official HMWSSB website (place "HMWSSB Building") |
| TGSPDCL Corporate Office | Google Maps embed on the official TGSPDCL website |
| TGPCB Head Office | Google Maps embed on the official TGPCB website (map centre; approximate) |
| HYDRAA Office | none: Nominatim found no reliable match, so no distance is shown |

## Known uncertainties

- GHMC helpline "21111111" is printed without the 040 STD code and without hours; not confirmed for CMC/MMC.
- The GHMC app page does not say which complaint types the app accepts.
- The TGPCB Janavani portal is on a non-government domain; it is listed only because the official site links it.
- HMWSSB's "Hyderabad - 4" is not a six-digit PIN, so `pincode` is empty.
- The Prajavani portal does not clearly say grievances can be filed online (it describes in-person sessions
  and status tracking).
- Jurisdiction boundaries between GHMC, CMC and MMC changed in 2026; the chatbot lists all three portals for
  municipal categories and does not decide which corporation covers an address.
- Re-verify all records before any real deployment; set a new `verified_on` when you do.
