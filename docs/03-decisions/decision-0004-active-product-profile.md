# Decision 0004: The active product profile

Date: 2026-10-20

## What was decided

The constants the potency engine uses by default are now **Set C** from the Phase 2C study: Ea/R = 15000 K and a shelf life of 8760 hours (12 months). The reference temperature (5 C) and the minimum potency (0.90) did not change. The team document's original values (Ea/R = 10000 K, 17520 hours) are kept as a **reference profile** in `config/product_team_document.yaml`.

## Why Set C

With the original constants the worst scenario spent under 9 percent of the shelf life, potency never fell below the minimum in any recording, and a falsified sensor hid a potency difference of under a fifth of a percentage point. That is hard to show in a pitch. The Phase 2C study measured five candidate sets on the same recordings. Set C gives a story that reads clearly:

- an ordinary 48 hour trip costs about half a percent of the shelf life, so nothing alarming shows;
- the heatwave leg visibly spends about 19 percent;
- the cooling failure takes potency below the minimum after about 32 hours;
- a falsified sensor hides about 14 percentage points of shelf life, which is about 50 days.

Set D was too steep (the cooling failure ended near 19 percent potency). Set B never crossed the minimum. Set E was steeper than needed.

## The labelling rule

Set C is an **illustrative profile for a heat-sensitive biologic**. It is not measured and not sourced. Wherever it appears it carries the words: "placeholder, not sourced [SOURCE NEEDED]; illustrative profile; replace with the manufacturer's stability data". Neither profile may be described as the data of a real product.

## Why the team document's profile stays

Two reasons. The document's worked examples (8 hours at 12 C uses 0.110 percent of the shelf life; 24 hours at 30 C uses 2.66 percent) are only true for its constants, and we want them to stay checkable. And we have not traced a source for the 10000 value, so we cannot call it verified either; the file says so. The reference profile holds only the product section. The box simulator and free-run settings live only in the active file, and a test checks that every other key in the two files is the same, so the two cannot drift apart.

## Consequence: constants are swappable

Product constants now live in profiles you load by path. Swapping in a manufacturer's stability data later means adding a third profile file and, if wanted, pointing the default at it. The shared test vectors exist for both profiles, and the TypeScript port must reproduce both.

## What changed with it

- A ninth scenario, `hidden_spoilage`, shows the new story: weak cooling and a falsified sensor over four days, where the reported series stays clean while the true potency crosses the minimum.
- The `potency` command now also prints the simulated hour at which potency first fell below the minimum.
- The old golden recordings did not change; the constants affect only the potency numbers, not the simulated temperatures.
