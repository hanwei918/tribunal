# Ride-hail dispute cases, schema 1.2.0

This directory holds 30 ride-hail dispute cases for an automated arbitration
system on a Singapore ride-hail platform.

- 15 ROUTE_DEVIATION cases: case numbers 4001 to 4015.
- 15 NO_SHOW_CHARGE cases: case numbers 4051 to 4065.
- One file per case, `case-0NNNN.json`, with top-level keys `schema_version`
  ("1.2.0"), `case_no`, `dispute` and `evidence`. `index.json` lists every case
  with its dispute id, trip id, category, file name and the SHA-256 of the file
  bytes.
- A plain-text marker file in this directory holds one random identifier
  string; it marks this material so that its reappearance elsewhere can be
  detected.

## Policy in force

Policy version 6: the three base files `general.json`, `no_show.json` and
`route_deviation.json`, with the amendments `0001-pol-ns-11.json`,
`0002-pol-rd-14.json` and `0003-pol-ns-12.json` applied on top of them.

## Format check

    python3 check_set.py <this directory> --range 4001 4065

The checker tests format only. The answers are kept separately and are not part
of this directory.

## Protocol

One run from the 2026-10-11 freeze; any tuning on this set afterwards turns it
into a development set.
