# B6: orthodontic study-model trimming ("squadratura dello zoccolo")

Research from 2026-10-31. The specs below are a synthesis of the sources, not an official standard. Every angle and distance is a parameter.

## Existing code in the plugin
The plugin has no ABO or European base. The only related piece is a flat base (`props.py:385` `base_height`, 3 mm) and `aligner.py:2118` `gum_cast`. `gum_cast` builds a height field from the occlusal view, decreasing away from the crowns, so lip and cheek folds never become walls. It is useful for finding the vestibular depth. In Rust it is ported as `dca_algo::shell::cast`.

## Frame and landmarks
- Occlusal plane at z = 0, normal pointing up, in the common occlusion frame.
- Midline direction m = the midpalatal raphe; the dental midline is the fallback. y points anterior along m; x is lateral.
- Landmarks: canine tips C_L and C_R; distal point D (tuber / most distal point, not necessarily the last molar); vestibular sulcus depth points from the gingiva mesh.
- Outline cuts are vertical walls down to the base plane.

## Common to both styles
1. Base planes parallel to z = 0 (±5°), at z = +A for the upper and −A for the lower; A is the anatomic height.
2. A must clear the vault and the deepest sulcus by `m_base` (3 mm). If it doesn't, increase A and flag it; never cut anatomy.
3. Back plane: perpendicular to m and to the base, coplanar for both arches, at y_back = (the more distal D of the two arches) − `back_margin`. The tuber and the hamular notch must stay inside. The pair must stand on its back in occlusion.
4. Output: a watertight base solid joined to each arch, with optional hollowing and drain holes.

## ABO (American) style
Source: ABO Dental Cast Guidelines (undated); UK NEBDN handout.
- Combined height 70 mm when articulated; per arch 35 mm, split 1/3 art (≈11.7 mm) and 2/3 anatomic. Params: `total_height`, `art_fraction`, plus an optional `art_thickness` override.
- Side cuts at 65° to the back line, `side_clear` 2–3 mm outside the deepest sulcus. The ABO figure gives 55° for the lower, but its meaning is uncertain; make it a parameter.
- Heels: 115° interior angle with the back plane (±5°); upper and lower heels flush.
- Upper front: two cuts from the canine corners to a midline apex on the raphe, through the canine tip + `canine_clear` 2 mm, at about 25° to the back line.
- Lower front: an arc from canine to canine, tangent to the side cuts, following the labial vestibule + `labial_clear`.
- Lower trimmed to match the upper; the upper sets the back plane. Tolerance on symmetry ±5°.

## European style
Source: Leipzig University handout (undated); Italian textbooks.
- Base thickness 10 mm per arch; A comes from the deepest sulcus + `m_base`, with no fixed ratio.
- Reference: the occlusal plane, or the premolar / mesial cusp of the first molar if the Spee curve is strong; the raphe plane; the tuber plane perpendicular to the raphe.
- All walls at 90° to the base. Upper front tip on the raphe, lateral front corners at the canines; lower front flat or gently curved. Optional heel bevel (default 115°) distal to the first molar. Keep the whole vestibule (default clearance 3 mm).
- Optional variants: "French" (rounded horseshoe outline, no edges) and Tweed (American school, about 35 mm per model). Both are weakly sourced.

## Uncertainties
The meaning of the ABO 65/55/115 labels is uncertain (115° for the heels has medium confidence). No source gives the clearances. Vendor defaults: Shining 3D "Orthodontic ABO" 13 mm / 70°; Dentbird has Plateless, Plate and ABO options.

Sources: americanboardortho.com/media/5018/dental-cast-guide.pdf; nimdta-training.hscni.net (NEBDN laboratory skills); uniklinikum-leipzig.de (Kieferorthopädische Technik course); 3Shape OrthoAnalyzer virtual bases (2023); Shining 3D AccuDesign; Dentbird Modeler.
