# Changelog

## Unreleased
- Add a performance test on a 5,000-customer export (the size of the new EMEA batch).

## 0.3.0
- Normalise accents before matching, so "José" and "Jose" count as the same name.

## 0.2.0
- `find_duplicates()` returns pairs sorted, with the alphabetically smaller name first.

## 0.1.0
- First version: Levenshtein-based duplicate detection for the CRM import.
