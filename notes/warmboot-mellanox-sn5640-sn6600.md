# Warmboot Notes (Mellanox)

## SP5
- **Qualifications (per Mellanox):**
  - `202605` qualified
  - `202511` qualified
- **Backend / topology:** MAI backend ToR
- **Warmboot status:**
  - Mellanox claims warmboot works.
  - Perform warmboot validation here first.
- **Platform:** `Mellanox-SN5640`

## SP6
- Retiring the **2-bank approach**
- Moving to **Broadcom (BRCM) approach**
- SONiC appears to run at least partially
- Warmboot status unknown; this requires validation
- **Platform:** `Mellanox-SN6600`

---

## Initial Warmboot Plan (SN5640)
Start with the `Mellanox-SN5640` platform and execute warmboot in this order:

1. `202511` same-image warmboot
2. `202605` same-image warmboot
3. Warmboot upgrade from `202511` → `202605` (only if same-image warmboot passes)

> Always collect **techsupport** after each warmboot test.

---

## Additional Context / Risks
- Using SONiC neighbors is commonly problematic in this scenario.
- Prefer **cEOS neighbors** and use the `internal-202605` branch.
- It is uncertain whether warmboot with exactly the same from/to image will always work.

---

## Simplified Manual Validation Flow (Do this first)
Before pipeline automation, simplify and validate manually:

1. SSH to the device manually.
2. Set SONiC installer so **next boot = current image**.
3. Run warm reboot:
   ```bash
   sudo warm-reboot -vvv
   ```
4. After boot, verify:
   - No `syncd` (or related) crashes
   - All expected Docker containers are up
   - BGP sessions are up
5. Collect **techsupport** artifacts.
6. Once manual validation is stable, move the flow into CI/pipeline and identify failure points there.
