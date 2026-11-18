# Turntable scanning with a structured-light depth camera (MINI 2): research, 2026-11-18

**Answer in brief.** Revo Scan feeds the turntable motion into a free-tracking SLAM front end (feature or marker mode). The table is only a motion aid, and I found no evidence it uses the angle as a pose prior (inference, see gaps). We know the angle, so we can do better: **stop-and-capture, pose = calibrated axis x commanded angle, ICP only to refine 1-3 DoF on object-only points (cylinder ROI), then re-integrate after a pose-graph pass.** Most "loses the object / slow / calibration fails" symptoms come from using free 6-DoF tracking with a static background in the cloud, and from fitting the axis out of those tracked poses (circular).

Code facts (dentalcraft-core, read just now): `tracking.rs` uses frame-to-model projective point-to-plane ICP with constant-velocity prediction, gates [3,1.2,0.5] mm, 6 iterations per stage, 8000 samples. `rig/fit.rs` fits the axis from tracked camera poses. `jobs.rs` calibrates while the table turns at 30 deg/s. At ~8 fps that is 3.75 deg/frame, which is ~2.0 mm per frame at r=30 mm and ~2.9 mm at r=45 mm, against a 3 mm coarse gate (my arithmetic). Tracking therefore sits at the edge of its basin before the background even matters.

## Ranked techniques to adopt

### 1. Stop-and-capture with the angle as the pose prior (highest value)
- **Why.** In continuous mode a user on the Revopoint forum saw smearing and ellipse-shaped marker dots, and fixed it by rotating ~5 deg and capturing 2 single frames, 72 times (fxtentacle, 2024-03-07, https://forum.revopoint3d.com/t/feature-request-turntable-single-frame/24149). Another user's OpenScanTable stops every 20 deg per shot (https://forum.revopoint3d.com/t/openscantable-for-mini/23982). The Revopoint community manager (PUTV) says the opposite: continuous, fluid motion, 90 frames or fewer, no overscan. His arguments concern Revo Scan's duplicate accumulation, which a TSDF does not have. Revo Scan 5 guide: single-shot frames need >=50% overlap (https://dl.revopoint3d.com/document/soft/revoscan-android-userguide-en-v5.4.0-20250312.pdf).
- **Parameters.** Step 10 deg (36 stops/rev; range 5-15 deg). Move at 20-30 s/rev. Wait for `+OK,TURNANGLE` completion (a 30 deg move completes ~1.5 s after the ack, BLE skill). Settle 0.3-0.5 s. Capture 3-5 frames at the stop (6.5-10.7 fps, ~0.5 s). Take a per-pixel median over valid samples, which cuts depth noise by ~sqrt(n). Reject a stop if inter-frame depth RMS is >0.1 mm (still moving). Read CHANGEANGLE once at rest. Expect ~70-80 s per revolution (my estimate).
- **Continuous fallback.** Only at the slowest speed (90 s/rev = 4 deg/s = 0.5 deg/frame). Table angle polls are not frame-synchronous: a 100 ms latency at 20 deg/s is 2 deg of prior error. Fit theta(t) = theta0 + w(t - t0) to timestamped polls (the u32 ms frame header) and refine only delta-theta with ICP.

### 2. Axis calibration: from the object (no target), and with a sphere target
**2a. Without a target (any asymmetric, matte, non-flat object >=20 mm):**
1. Coarse axis direction: RANSAC plane of the platter at tilt 0 (3 points, 1000 iterations, ~0.5 mm threshold, then LS on inliers). Horus does the same, taking the circle plane normal of tracked points as the axis. Cross-check with the IMU accelerometer gravity vector from the frame header (axis is vertical at tilt 0, scanner static).
2. At each stop, register stop i to stop i+1 with point-to-plane ICP seeded with the commanded Rz(dtheta) (2 levels, gates 2 mm then 0.5 mm, ROI points only). Per pair, the screw axis is the null vector of sum (R-I)^T(R-I). The axis point c solves (I-R)c = t by least squares. The measured rotation angle also gives the angle gain (expect 1.00 +/- 0.005; the table's real deg/step is not guaranteed). `fit.rs` already implements this, but feed it seeded pairwise ICP, not free-tracked fused poses.
3. Alternate, as Pang et al. do (https://www.cs.cityu.edu.hk/~rynson/papers/cga14.pdf): rotate the next scan with the current axis, ICP-refine, re-estimate the axis, keep the axis with more correspondences. They report average error 0.197 vs 0.597 for the two-sphere method on the same object (their units, structured light at ~760 mm, 30 deg steps). Their initial registration is 4PCS + ICP; ours is seeded by the prior.
4. Final polish: Gauss-Newton on 5 parameters (axis direction 2, axis offset in the plane perpendicular to the axis 2, angle gain 1) minimising point-to-plane residuals of all overlapping stop pairs (|dtheta| <= 40 deg) plus the 360-deg closure pair.
5. Quality gates: per-pair RMS <= 0.1 mm. 0-to-360 deg closure gap <= 0.1-0.15 mm. An axis offset error e shows up as up to 2e between views 180 deg apart, so e <= 0.05 mm (my arithmetic).
- **Pitfall.** Slippable objects (flat, cylindrical or conical about the axis) are unusable as calibration objects (Pang et al. section 7). Add Blu-Tack beads or use the sphere target.

**2b. With a target (one-time install; re-run if scanner or table moved):** one matte sphere, 15-25 mm diameter, off-axis at r~25-40 mm.
- Sphere LS fit per stop on the depth data: 12 stops x 30 deg, or the 36-stop pass. Fix the radius to the median.
- The centres lie on a circle: plane fit gives the axis direction, circle fit gives the axis point. This is exactly Horus `platform_extrinsics.py` (fit_plane + fit_circle in the plane; sanity check |t - estimate| < 100 mm): https://github.com/bqlabs/horus.
- A second sphere at another height, or two heights, adds redundancy (Li et al. sphere method, cited in Pang and Bisogni).
- Gate: circle residual RMS <= 0.05 mm [my target, unverified].
- Checkerboard only works if IR images are used (800x1200 format has rectified IR); spheres suit a depth-only stream better.
- **Dual axis, tilt.** Joint fit of two axes intersecting at q (omega1.omega2 = 0, p' = R1(th1) R2(th2) (p - q) + q), nonlinear LS; wider pose dispersion is better (Bisogni et al. 2020, https://pmc.ncbi.nlm.nih.gov/articles/PMC7764672, used 8 deg tilt x 20 deg turn steps). The tilt readback is fake (always 0.5, BLE skill), so measure the real tilt per pass as the angle between the fitted platter normal and the calibrated axis. Do not trust the commanded tilt.

### 3. Segmentation: remove the static background from the ICP, in the object frame
- The camera is static, so every background point votes "no motion" and pulls ICP to identity. Run ICP in the object frame: rotate frame points by the prior, and match them against a model built only from ROI points. Then the background cannot enter the source set at all.
- **Cylinder ROI in the table frame** (Horus `point_cloud_roi.py`: keep 0 <= z <= h and rho <= r): z from the fitted platter plane + 0.5-1 mm (exclude the platter, so its plane and contact band do not slide-constrain), rho <= r_obj + 3 mm, z <= h + 3 mm. Project the cylinder to a pixel box for early rejection, then test per point in 3D. At tilt, the cylinder tilts with the platform (full T_tilt x T_turn). Repo defaults are r=45 mm, h=60 mm, 1 mm below the platter.
- **Secondary:** a background depth frame of the empty platter, one per tilt. The platter is rotationally symmetric, so one frame per tilt is enough. Tolerance max(3 sigma, 0.5 mm); `jobs.rs` uses 1.5 mm. It cuts the object base, so it is not the primary method.
- **Depth gate:** platter-centre depth +/- (r + h). Revo Scan has the same two ideas in its UI: a "Scanning Distance" slider and a "Base Removal" toggle (Revo Scan 5 guide).
- Drop depth-edge pixels (existing max_slope 4 = ~76 deg) and speckles; keep the existing ~30 deg normal gate.

### 4. ICP as a constrained refinement with failure detection
- Pose = T_table(theta_cmd) o correction. Normal operation: correction is 1 DoF (delta-theta about the axis). On a high residual, widen to 3 DoF (delta-theta + 2 in-plane axis offsets, +/- 0.3 mm). Use free 6-DoF only for diagnostics. Add Tikhonov lambda on the correction.
- **Stability test:** eigenvalues of the 6x6 point-to-plane covariance (Gelfand et al. 2003, https://graphics.stanford.edu/papers/stabicp/stabicp.pdf; PCL `CovarianceSampling`). If the condition number is high, keep the prior and flag the stop. KinectFusion does the same with a null-space check plus a step-size threshold, and drops to relocalisation (Newcombe 2011, section 3.5).
- **Normal-space sampling:** 2-4k samples, uniform over normal bins (Rusinkiewicz-Levoy; Gelfand extends it with torque directions). It keeps few-feature objects constrained.
- **Pyramid:** KinectFusion uses 3 levels with [4,5,10] iterations coarse to fine (160x120, 320x240, 640x480; ICPCUDA README: https://github.com/mp3guy/icpcuda, 755 Hz on a Titan X). With a prior, 2 levels of [3,5] with gates 1.0 -> 0.4 mm are enough. Reject if |delta-theta| > 1.5 deg or RMS > 0.1-0.2 mm. On rejection, fuse with the prior pose and mark the stop uncertain. Never drop it, so tracking cannot lose the object.
- **Projective vs kd-tree:** projective association is O(N) and exact for tiny motions, which is our case with a prior. Use the kd-tree only for the pairwise axis fit.
- **Colored ICP** (Park 2017, Open3D: radii [0.04,0.02,0.01] with [50,30,14] iterations, https://www.open3d.org/docs/release/tutorial/pipelines/colored_pointcloud_registration.html): low priority. Colour is not aligned to the depth stream without vendor calibration, and the rectified IR frames carry the projector pattern (inference).

### 5. Fusion: sparse TSDF, ROI only, two-phase resolution
- **Sparse blocks:** hashed blocks of 8^3 (InfiniTAM) or 16^3 (Open3D VoxelBlockGrid). Allocate only blocks inside the truncation band of ROI points (Niessner 2013 voxel hashing). Never allocate a dense volume: 400^3 voxels at 0.1 mm is ~0.5 GB.
- **Live model (tracking, preview):** voxel 0.25 mm, truncation 1.0 mm (4 voxels). InfiniTAM defaults are voxel 5 mm, mu 20 mm (4 voxels), maxW 100. Open3D's example uses 7.8 mm / 40 mm (5 voxels), and its docs say a finer voxel is "susceptible to depth noise".
- **Final pass:** re-integrate stored ROI depth crops with the refined poses at 0.1 mm voxel, truncation >= 3 x (pose RMS + depth sigma) (0.4-0.5 mm). Revo Scan fuses at a point distance of 0.05-0.2 mm, and its forum guidance is to mesh at the fusion distance (0.02 mm fusion was grainy). A crop of ~300x300 px x 2 B ~ 180 KB per frame, so ~72 MB for 400 frames. This is BundleFusion-style re-integration after optimisation, without the GPU.
- **Weights:** w = 1 (KinectFusion: a simple average works), or cos(angle) between normal and view ray with cos < 0.2 dropped. Cap W at 50-100.
- **Frame budget** (sensor 95-150 ms/frame): ROI mask + normals <= 10 ms, ICP <= 15 ms (2 levels, 4-8k points), integrate <= 20 ms (~25k valid ROI px x ~9 voxel updates ~ 2e5 updates; my estimate). Raycast the tracking model once per stop (<=220 px wide, as in the repo), not per frame. With stop-and-capture there is no real-time constraint at all (<= 200 ms per stop).
- **Fuse every Nth:** continuous mode, key-frame on d-theta >= 3 deg (~1.5 mm at r=30 mm). At 1 deg spacing a surface point is seen 100+ times, which is wasted. KinectFusion showed frame skipping (every 8th frame) reduces frame-to-frame drift, but frame-to-model tracking was drift-free.

### 6. Relocalisation, loop closure, multi-pass
- **Relocalise with the prior, not features:** 1-D search over delta-theta in +/-10 deg (0.5 deg steps) scoring point-to-plane residual, then ICP. Use FPFH only when the object itself moved or slipped (all delta-theta fail): voxel ~1 mm, normal radius 2 x voxel, FPFH radius 5 x voxel, RANSAC 3 points, distance 1.5 x voxel, edge-length checker 0.9, 100k iterations at 0.999 confidence, or Fast Global Registration (Open3D global registration tutorial). InfiniTAM v3 does this with a random-ferns relocaliser plus tracking-failure detection. Open3D's own dense SLAM has no relocalisation and is "not optimized for accuracy".
- **Pose graph per revolution:** nodes = stops, odometry edges between neighbours (uncertain=False) with ICP information matrices, one loop edge stop 0 - stop 36 (uncertain=True), Open3D multiway: LM, max_correspondence_distance = 1.5 x voxel, edge_prune_threshold 0.25, reference node 0 (https://www.open3d.org/docs/release/tutorial/pipelines/multiway_registration.html). With a known axis the unknowns reduce to the 5 axis parameters + 36 delta-theta_i (prior sigma ~0.2 deg). That is a tiny problem. The loop gap doubles as the calibration health metric.
- **Tilt multi-pass:** Revopoint's advice is to keep the table horizontal for small objects and re-place the object, or tilt scanner and table toward each other, never away (it lengthens the distance and hides the markers): https://global.revopoint3d.com/blogs/blog/dual-axis-turntable-and-app-tips. Pass A at tilt 0, B and C at +/-tau (measured tau). One rigid node per pass, ICP edges between overlapping passes (PUTV: keep ~20-30% overlap when merging), same graph. Fix the object with glue tack.
- **IMU:** the scanner is static on a turntable, so the gyro ~0 and gives no pose prior. Use the accelerometer only to cross-check the axis against gravity and to detect "scanner was bumped" (then invalidate the calibration). Do not use it as an ICP prior.
- ElasticFusion (ICP + RGB with w_rgb=0.1, local/global loop closure with ferns, ~31 ms/frame on a GPU), Kintinuous and BundleFusion target room-scale handheld motion and need GPUs. Skip.

### 7. Revo Scan workflow facts to match (and beat)
- Modes: Accuracy Standard / High / High-speed. Tracking Feature (no repeating patterns) / Marker (6 mm markers for MINI, 5+ per frame, 1-2 cm apart) / Global Marker. Object type General / Dark / Face / Body. Depth exposure is set until there are as few blue (under) and red (over) patches as possible (Revo Scan 5 guide, section 5.2.1). A distance bar shows green when optimal.
- Distance: for MINI 2, Revo Scan's "Excellent" is 170-200 mm, 120-170 mm is "Too Near" (user report, 2025-07-03: https://forum.revopoint3d.com/t/mini2-view-angle-and-best-working-distance/38719; the spec range is 120-250 mm). Our ~200 mm sits at the far edge of Excellent. Try 180-190 mm. PUTV: ~45 deg view is best for undercuts.
- Aids: reference objects, Magic Mat, Turntable Topper (pre-placed markers), scanning spray or powder for dark / shiny surfaces, a dim room (avoid cool-white LED).
- Revo Scan has a "Sync" option that starts and pauses the turntable and scanner together, and turntable templates (angle, speed, direction). No axis calibration for the dual-axis table was documented anywhere I could read (see gaps).
- Our constraints (skill): no vendor commands; only V4L2 brightness/gain; exposure locked to auto; depth unit 1/200 mm; 8-18% of pixels valid; fps 2.75-10.7 depending on exposure.

## Open-source references (what they do)
- Horus / Ciclop (https://github.com/bqlabs/horus, GPL-2): pattern origin positions over turntable angles -> plane fit -> circle fit in the plane -> axis normal + centre; cylinder ROI. FabScanPi docs describe Ciclop-based hardware; I did not verify its calibration code.
- Open3D: legacy reconstruction pipeline (make fragments -> register fragments with FPFH/FGR -> refine -> integrate with ScalableTSDF) built on Choi 2015; multiway registration; tensor VoxelBlockGrid; `t.pipelines.slam` frame-to-model (https://www.open3d.org/docs/release/tutorial/t_reconstruction_system/dense_slam.html).
- KinectFusion: 3-level ICP [4,5,10], projective association, 256^3 voxels in its turntable loop test (560 frames; frame-to-model closed the loop with small drift, frame-to-frame did not): http://www.doc.ic.ac.uk/~ajd/Publications/newcombe_etal_ismar2011.pdf.
- InfiniTAM v3 (https://arxiv.org/html/1708.00783v1, settings: https://github.com/victorprad/InfiniTAM): hash blocks 8^3, extended depth tracker (levels "rrbb", numiterC 20, numiterF 50), failure detection, ferns relocaliser, submaps.

## Pitfalls checklist
- Do not fit the axis out of poses tracked on the fly. Do not calibrate at 30 deg/s. Do not let the background (or the platter) into the ICP source set.
- Do not trust the commanded tilt, nor a polled angle during motion.
- The angle prior is wrong if the object slips on the platter: detect it (all delta-theta residuals high), then relocalise with FPFH.
- Symmetric or flat calibration objects make the axis unobservable.
- Scanner re-enumerates 1.5-2.5 s after stop (USB skill), and the table accepts one central: capture and table control must not restart the stream between stops.

## Uncertainties and gaps
- Revopoint's own dual-axis calibration procedure: **not found**. Support pages returned 403 / login (Cloudflare), Revopedia manuals are JS-rendered, and the quick-start PDFs gave no text. "Revo Scan does not use the angle as a prior" is **inference** (forum behaviour: tracking errors accumulate, markers or reference objects are needed, "Sync" only starts both devices). Confidence: medium-low.
- Sources conflict on stopping the table: fxtentacle (+ OpenScanTable) say stop-and-capture is better; PUTV says continuous and fluid. I follow the physics (smear, latency) and our TSDF; the first is a user observation, not a controlled test.
- Frame-budget numbers, "70-80 s/rev", sphere-fit accuracy, and the 0.05-0.15 mm gates are my estimates. They need measuring on the real data in /var/tmp/dc-scan-data.
- Pang et al. numbers use their scanner and units; they are not MINI 2 numbers.

## Sources (accessed 2026-11-18)
- Pang et al., "A Tool-free Calibration Method for Turntable-based 3D Scanning Systems", IEEE CG&A 2014: https://www.cs.cityu.edu.hk/~rynson/papers/cga14.pdf
- Bisogni et al., Sensors 20(24):7107, 2020-12-11: https://pmc.ncbi.nlm.nih.gov/articles/PMC7764672
- Horus platform_extrinsics.py / point_cloud_roi.py (Copyright 2014-2016): https://raw.githubusercontent.com/bqlabs/horus/develop/src/horus/engine/calibration/platform_extrinsics.py
- Newcombe et al., KinectFusion, ISMAR 2011 (URL above); ICPCUDA README; Gelfand et al., 3DIM 2003 (URL above); Whelan et al., ElasticFusion, RSS 2015: https://www.imperial.ac.uk/media/imperial-college/research-centres-and-groups/dyson-robotics-lab/twhelan_etal_rss2015.pdf
- Open3D 0.19 docs: global registration https://www.open3d.org/docs/release/tutorial/pipelines/global_registration.html, RGBD integration .../pipelines/rgbd_integration.html, t_reconstruction_system/config.py (trunc_voxel_multiplier).
- Revo Scan 5 Android guide v5.4.0 (2025-03-12); Revopoint blog "Dual-axis Turntable and App Tips" (2023-02-09); Revopoint forum threads linked above (2024-03 to 2026-08).
