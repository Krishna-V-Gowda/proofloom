# ADR 0002: represent money in integer paise

**Status:** accepted

Every consequential amount is stored and compared as an integer currency subunit. No floating-point tolerance is used to decide whether a settlement ties out.

This makes the deliberately blocked 137-paise discrepancy exact and prevents binary floating-point behavior from becoming an undocumented policy.
