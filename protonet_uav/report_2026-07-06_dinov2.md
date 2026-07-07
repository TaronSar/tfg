# Daily Report — 2026-07-06

**Model enhancement: transition to DINOv2 backbone + Phase 0 baseline**

## 0. Summary

Today had two threads. First, I locked a trustworthy measurement baseline
(Phase 0): a per-identity verification-AUC harness with bootstrap confidence
intervals and EER, run at the operational crop-size envelope. Second, on the
strength of the diagnosis that the current MobileNetV3 encoder keys on background
and cannot separate look-alike UAVs, I decided to enhance the model by replacing
the backbone with a self-supervised DINOv2 encoder. Phase 0 is the baseline the
DINOv2 model must beat.

## 1. Why I am changing the backbone (DINOv2)

The current encoder is MobileNetV3 pretrained on ImageNet, fine-tuned on my UAV
crops. Two structural weaknesses were established in prior sessions and motivated
the change:

- **Background keying.** Grad-CAM showed the model attending to the sky rather
  than the airframe; removing the background flipped scores the right way (a true
  target rose 0.34 → 0.69, a similar impostor fell 0.71 → 0.49). The encoder was
  using context, not the aircraft.
- **Look-alike collapse.** Visually similar UAVs (large fixed-wing / UCAV types)
  land in nearly the same region of embedding space, so no threshold separates
  them.

DINOv2 addresses the root cause rather than the symptom:

- It is trained self-supervised to attend to objects, not background, which is
  expected to reduce the sky-keying directly.
- Its dense, patch-level features are far richer than MobileNetV3's, which is
  what fine-grained discrimination between similar airframes actually needs.
- Used as a strong frozen backbone with only a small trainable head, it also
  attacks my overfitting problem (train 1.000 vs val ~0.81): fewer trainable
  parameters means far less capacity to memorize training identities.

**Note on version:** I chose DINOv2 for licensing (Apache-2.0, safe for a
commercial Embention deployment) and ecosystem maturity. DINOv3 has stronger
dense features and is the better pure-research choice, but its more restrictive
license must be reviewed before any product use. This is flagged as an open
decision.

## 2. Phase 0 — the measurement baseline (what and why)

Before changing the model I built a harness that produces one honest, stable
number to measure every future change against. Design choices and their reasons:

- **Per-identity verification AUC** (one identity's genuine queries vs all other
  identities as impostors), because deployment is binary verification, not
  ranking.
- **Bootstrap 95% confidence intervals** (n_boot=2000), so I can tell a real
  difference from sampling noise on small identities.
- **EER** (equal-error rate) reported alongside AUC, because AUC is a ranking
  measure and EER gives an interpretable error rate at the balanced operating
  point.
- **Evaluated at the operational crop-size envelope**, because the deployment
  target is far-away UAVs; a model that only works on clean close-ups is useless.

**Crop-size audit** (val, `data\uav_dataset_yolox_crops_removed_lt30`):

```
186 crops | longer side: p5=30 p25=40 p50=52 p75=63 p95=80 | min 18 max 92
100% of crops are already <=143px; 68% are <=60px; none are >=200px.
```

Consequence: the crops are **already** at operational size. The
`DegradeToOperational` augmentation only shrinks (never enlarges) and only when
its random target lands below a crop's current size, so at these sizes it is
roughly a 90% no-op. This was confirmed empirically (Section 3): `degrade_p=1.0`
and `degrade_p=0.0` give statistically identical results. Degradation of the
queries is therefore redundant here; its real value is in training, to bring the
large clean enrollment images down to operational scale.

**Caveat surfaced by the audit:** Blender-rendered small crops are small but
*sharp*, whereas real far-away UAV crops are small **and** blurry/noisy/
compressed. Size is matched; image quality is not. The baseline may therefore be
mildly optimistic versus real footage. An always-on blur/noise/JPEG augmentation
(decoupled from size) is the honest missing piece and is proposed as follow-up.

## 3. Phase 0 results (baseline to beat)

- **Checkpoint:** `checkpoints_yolox_crops_mixed_domain_real\best.pth`
- Backbone MobileNetV3 | embed_dim 128 | metric euclidean | normalize True
- Val: 13 scored identities (3 skipped for too few images/no gallery) | k_shot 5

**Global** (pooled 122 genuine vs 580 impostor scores):

| degrade_p | AUC | 95% CI | EER |
|-----------|--------|----------------|-------|
| 1.0 | 0.8750 | [0.843, 0.905] | 0.205 |
| 0.0 | 0.8687 | [0.836, 0.899] | 0.213 |

→ 0.006 apart, CIs overlap almost fully: degradation is a no-op here, as
predicted by the size audit. **Baseline: AUC ~0.87, EER ~0.21.**

**Per-identity** (degrade_p=0.0), sorted worst to best:

| Identity | n_g | n_i | AUC | 95% CI | EER |
|----------|----:|----:|-------|----------------|-------|
| uav_3 | 25 | 58 | 0.7055 | [0.582, 0.817] | 0.328 |
| wing_loong_i_uav_war_thunder | 18 | 58 | 0.7299 | [0.601, 0.846] | 0.376 |
| baykar_k2_kamikaze | 7 | 58 | 0.8202 | [0.650, 0.951] | 0.404 |
| general_atomics | 11 | 58 | 0.8495 | [0.735, 0.948] | 0.190 |
| uav_gerbera_low-poly | 5 | 58 | 0.8897 | [0.803, 0.962] | 0.186 |
| orion_uav_war_thunder | 21 | 58 | 0.9376 | [0.881, 0.979] | 0.155 |
| heavy_killer_drone | 10 | 58 | 0.9379 | [0.874, 0.986] | 0.103 |
| bayraktar_kalkan_diha | 15 | 58 | 0.9724 | [0.934, 0.998] | 0.069 |
| Ukraine_pavilion | 7 | 58 | 0.9778 | [0.938, 1.000] | 0.052 |
| aai_rq2_pioneer_uav | 3 | 58 | 1.0000 | [1.000, 1.000] | 0.000 |

**Reading the results:**

- The trustworthy number is the **global AUC ~0.87 / EER ~0.21** (pooled, large n).
- `aai_rq2` "1.000" is a tiny-sample artifact (n_g=3): all three genuine queries
  happened to outrank the impostors and the bootstrap resamples the same three
  points, collapsing the CI to a fake [1,1]. Not real perfection.
- `baykar_k2` (n_g=7) has a genuinely wide CI [0.650, 0.951]; flagged for more
  frames. Low-n identities (aai_rq2, baykar_k2, uav_gerbera, Ukraine_pavilion)
  are provisional.
- **Most striking finding:** `wing_loong` collapsed. In earlier clean-resolution
  analysis it was the most distinctive identity ("good anchor"); at operational
  size it is the 2nd worst (0.73, EER 0.38). At 40–60px a large fixed-wing looks
  like every other fixed-wing. This quantifies the resolution floor directly and
  is strong evidence that the remaining ceiling is set by representation quality
  — exactly what the DINOv2 backbone targets.

## 4. What this means

- The measurement is now honest and stable: operational **AUC ~0.87, EER ~0.21**,
  with CIs so I do not over-read noise.
- Query-side degradation is redundant at these crop sizes; the missing realism is
  blur/noise/compression, not size.
- Per-identity ceilings track visual distinctiveness **at operational size**, and
  large fixed-wing types lose their distinctiveness there → the limit is the
  encoder's features, not the decision rule.
- This is precisely the case for a stronger, object-centric backbone. DINOv2 is
  the chosen enhancement; its result will be measured against 0.87 / 0.21.

## 5. Next steps

1. Integrate the DINOv2 backbone (frozen or lightly adapted) with the existing
   projection head; keep enrollment background-removed.
2. Evaluate DINOv2 on the **same** harness (per-identity AUC + CI + EER,
   operational size) and compare to baseline 0.87 / 0.21.
3. Add pairwise hard-pair AUC at operational size (the look-alike floor) so the
   DINOv2 gain on the hard cases is visible, not averaged away.
4. Collect more query frames for low-n identities to tighten their CIs.
5. Add always-on blur/noise/JPEG realism so the eval reflects real far-crop
   quality rather than Blender-clean small crops.
6. Review the DINOv2 vs DINOv3 licensing decision before any deployment use.

**Baseline frozen for comparison: operational AUC 0.87, EER 0.21.**
