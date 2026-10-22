"""Edited-text detection: finds words that were typed or pasted onto a document image after it was captured.

Genuine text on a card went through the same printer and the same camera or scanner as everything around it,
so every word shares the same edge blur, background noise and ink texture. A name typed over the card in an
image editor does not: its edges are sharper than the rest of the text, it usually sits on a flat patch that
was painted over the old name, and its ink is one uniform colour. Every OCR line is split into words and each
word is compared with the other words on the same document; a word is reported only when several of these
signs agree, so the check adapts to each photo and stays quiet on documents that are uniformly crisp
(digital e-cards) or uniformly blurry.
"""
import re

import cv2
import numpy as np

# Words compared with each other: Latin-script text read with reasonable confidence. Hindi lines come back from
# RapidOCR as noise, and Devanagari words are skipped anyway (their long head-line stroke reads as "sharp").
_LATIN_TEXT = re.compile(r"^[A-Za-z0-9 .,:;/'()&@#+\-]+$")
_MIN_OCR_SCORE = 0.60
_MIN_WORDS = 4          # reference words needed before a document can be judged
_MAX_DIM = 3000         # forensic image cap; larger photos are downscaled once

# Immerkaer noise estimator kernel (fast, robust estimate of sensor noise on flat background).
_NOISE_KERNEL = np.array([[1, -2, 1], [-2, 4, -2], [1, -2, 1]], np.float32)
_NOISE_SCALE = float(np.sqrt(np.pi / 2) / 6.0)
_K3 = np.ones((3, 3), np.uint8)


def prepare_image(image):
    """Grayscale array used for the forensics, from the full-resolution upload (PIL image)."""
    gray = cv2.cvtColor(np.asarray(image.convert("RGB")), cv2.COLOR_RGB2GRAY)
    h, w = gray.shape
    if max(h, w) > _MAX_DIM:
        f = _MAX_DIM / float(max(h, w))
        gray = cv2.resize(gray, (int(w * f), int(h * f)), interpolation=cv2.INTER_AREA)
    return gray


def _ink_mask(crop):
    """Text pixels of a crop (Otsu split, text = minority class), as a bool array."""
    thr, _ = cv2.threshold(crop, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    ink = crop < thr
    if ink.mean() > 0.5:
        ink = ~ink
    return ink


def _clip_box(box, w, h):
    x0, y0, x1, y1 = box
    return max(0, int(x0)), max(0, int(y0)), min(w, int(np.ceil(x1))), min(h, int(np.ceil(y1)))


def _background_stats(gray, region, exclude=None):
    """Noise level and flat-pixel share of the background (non-text) pixels of `region`."""
    x0, y0, x1, y1 = region
    crop = gray[y0:y1, x0:x1]
    if crop.size < 64:
        return None
    ink = _ink_mask(crop)
    bg = ~cv2.dilate(ink.astype(np.uint8), _K3, iterations=2).astype(bool)
    if exclude is not None:
        ex0, ey0, ex1, ey1 = exclude
        bg[max(0, ey0 - y0):max(0, ey1 - y0), max(0, ex0 - x0):max(0, ex1 - x0)] = False
    # border pixels of the crop have no full 3x3 neighbourhood
    bg[0, :] = bg[-1, :] = False
    bg[:, 0] = bg[:, -1] = False
    if bg.sum() < 40:
        return None
    f = crop.astype(np.float32)
    noise = np.abs(cv2.filter2D(f, cv2.CV_32F, _NOISE_KERNEL)) * _NOISE_SCALE
    resid = np.abs(f - cv2.medianBlur(crop, 3).astype(np.float32))
    return {"noise": float(noise[bg].mean()), "flat": float((resid[bg] < 0.5).mean())}


def _word_features(gray, box, line_h):
    """Edge sharpness, ink uniformity and background stats of one word."""
    H, W = gray.shape
    m = max(2, int(0.3 * line_h))
    x0, y0, x1, y1 = _clip_box((box[0] - m, box[1] - m, box[2] + m, box[3] + m), W, H)
    crop = gray[y0:y1, x0:x1]
    if crop.shape[0] < 8 or crop.shape[1] < 8:
        return None
    ink = _ink_mask(crop)
    ink_u = ink.astype(np.uint8)
    near = cv2.dilate(ink_u, _K3, iterations=2).astype(bool)
    core = cv2.erode(ink_u, _K3, iterations=1).astype(bool)
    edge = near & ~core
    bg = ~near
    if ink.sum() < 30 or bg.sum() < 30 or edge.sum() < 30:
        return None
    f = crop.astype(np.float32)
    ink_px = f[core] if core.sum() >= 20 else f[ink]
    ink_level = float(np.median(ink_px))
    contrast = abs(float(np.median(f[bg])) - ink_level)
    if contrast < 40:  # faint text: edge and ink measures are unreliable
        return None
    # Edge sharpness: gradient at the stroke edges relative to the local min-max range (so thin and bold strokes
    # compare alike). A one-pixel step scores ~1.0; print that went through a lens or scanner scores far lower.
    gx = cv2.Sobel(f, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(f, cv2.CV_32F, 0, 1, ksize=3)
    mag = np.sqrt(gx * gx + gy * gy)
    k7 = np.ones((7, 7), np.uint8)
    rng = cv2.dilate(f, k7) - cv2.erode(f, k7)
    valid = edge & (rng >= 0.5 * contrast)
    if valid.sum() < 20:
        return None
    sharp = float(np.percentile(mag[valid] / (4.0 * rng[valid]), 90))
    # ink texture: spread of the stroke cores relative to the text contrast
    ink_sd = float(np.std(ink_px) / contrast)
    stats = _background_stats(gray, (x0, y0, x1, y1))
    if stats is None:
        return None
    return {"sharp": sharp, "ink_sd": ink_sd, "ink": ink_level, "contrast": contrast, **stats}


def _has_headline(ink):
    """
    Devanagari words hang from an unbroken head-line (shirorekha) in their upper half, longer than the text is tall.
    Latin letters never draw a horizontal stroke that long, and leave gaps between letters.
    """
    height = ink.shape[0]
    for row in ink[: max(1, int(height * 0.5))]:
        if row.sum() < 1.2 * height:
            continue
        edges = np.diff(np.concatenate(([0], row.astype(np.int8), [0])))
        runs = np.flatnonzero(edges == -1) - np.flatnonzero(edges == 1)
        if runs.max() >= 1.2 * height:
            return True
    return False


def _split_words(gray, box):
    """Splits a text line into word boxes using the column gaps of its ink."""
    H, W = gray.shape
    x0, y0, x1, y1 = _clip_box(box, W, H)
    h = y1 - y0
    if h < 8 or x1 - x0 < 8:
        return []
    ink = _ink_mask(gray[y0:y1, x0:x1])
    cols = ink.any(axis=0)
    gap = max(3, int(0.25 * h))
    words, start, run = [], None, 0
    for i, on in enumerate(cols):
        if on:
            if start is None:
                start = i
            run = 0
        elif start is not None:
            run += 1
            if run >= gap:
                words.append((start, i - run + 1))
                start, run = None, 0
    if start is not None:
        words.append((start, len(cols) - run))
    # fold fragments narrower than a character pair (punctuation, a stray mark) into their neighbour
    merged = []
    for a, b in words:
        if merged and (b - a < 0.9 * h or merged[-1][1] - merged[-1][0] < 0.9 * h):
            merged[-1] = (merged[-1][0], b)
        else:
            merged.append((a, b))
    out = []
    for a, b in merged:
        if b - a < 1.2 * h:
            continue
        if _has_headline(ink[:, a:b]):
            continue
        out.append([x0 + a, y0, x0 + b, y1])
    return out


def _median_excluding(values, i):
    others = [v for j, v in enumerate(values) if j != i]
    return float(np.median(others))


def analyze(gray, lines, scale=1.0, debug=False):
    """
    Compares every word of the OCR `lines` ({"text", "score", "box"} on the analysis image) with the rest of the
    document in the forensic grayscale image `gray` (`scale` = forensic pixels per analysis pixel).
    Returns {"checked": words compared, "judged": enough words to compare, "suspicious": [{"text", "box", "score",
    "reasons"}]}: one entry per altered line, its box (analysis pixels) covering the altered words.
    """
    words = []
    for line_no, line in enumerate(lines or []):
        text = str(line.get("text", "")).strip()
        if float(line.get("score", 0)) < _MIN_OCR_SCORE or not _LATIN_TEXT.match(text) or len(re.sub(r"\W", "", text)) < 3:
            continue
        box = [v * scale for v in line["box"]]
        line_h = box[3] - box[1]
        if line_h < 10:
            continue
        H, W = gray.shape
        lx0, ly0, lx1, ly1 = _clip_box(box, W, H)
        # Background just outside the line: the reference for "is the patch behind this text flatter than the card?"
        r1, r2 = int(0.6 * line_h), int(1.6 * line_h)
        ring = _background_stats(gray, _clip_box((lx0 - r2, ly0 - r2, lx1 + r2, ly1 + r2), W, H),
                                 exclude=_clip_box((lx0 - r1, ly0 - r1, lx1 + r1, ly1 + r1), W, H))
        for wbox in _split_words(gray, box):
            feats = _word_features(gray, wbox, line_h)
            if feats is None:
                continue
            words.append({"line": text, "line_no": line_no, "box": wbox, "ring": ring, **feats})

    result = {"checked": len(words), "judged": len(words) >= _MIN_WORDS, "suspicious": []}
    if not result["judged"]:
        return result

    sharp = [w["sharp"] for w in words]
    ink_sd = [w["ink_sd"] for w in words]
    flat = [w["flat"] for w in words]
    for i, w in enumerate(words):
        ref_sharp = _median_excluding(sharp, i)
        ref_ink = _median_excluding(ink_sd, i)
        ref_flat = _median_excluding(flat, i)
        reasons, points = [], 0

        d_sharp = w["sharp"] - ref_sharp
        sharp_note = f"edges {{}} than the rest of the printed text ({w['sharp']:.2f} vs {ref_sharp:.2f})"
        if d_sharp >= 0.20 and w["sharp"] >= 0.85:
            points += 3  # digitally crisp text on a document whose print is visibly blurred by the camera/scanner
            reasons.append(sharp_note.format("digitally crisp, much sharper"))
        elif d_sharp >= 0.15:
            points += 2
            reasons.append(sharp_note.format("much sharper"))
        elif d_sharp >= 0.10:
            points += 1
            reasons.append(sharp_note.format("sharper"))

        ring = w["ring"]
        if ring is not None:
            d_flat_local = w["flat"] - ring["flat"]
            d_flat_doc = w["flat"] - ref_flat
            if d_flat_local >= 0.12 and d_flat_doc >= 0.10:
                points += 2 if d_flat_local >= 0.18 else 1
                reasons.append("sits on a flat, painted-over patch (background noise missing)")
            elif ring["noise"] >= 1.0 and w["noise"] <= 0.62 * ring["noise"]:
                points += 1
                reasons.append("background behind the text is smoother than the card around it")

        if ref_ink >= 0.03 and w["ink_sd"] <= 0.45 * ref_ink:
            points += 1
            reasons.append("ink is one flat digital colour, unlike the printed text")

        w.update(ref_sharp=ref_sharp, ref_ink=ref_ink, ref_flat=ref_flat, points=points, reasons=reasons)

    by_line = {}
    for w in words:
        # Sharpness is the core sign; flatness/ink alone also occur on genuine bold or boxed print.
        if w["points"] < 3 or w["sharp"] - w["ref_sharp"] < 0.10:
            continue
        hit = by_line.get(w["line_no"])
        if hit is None:
            by_line[w["line_no"]] = {"text": w["line"], "box": list(w["box"]), "score": w["points"], "reasons": w["reasons"]}
            continue
        hit["box"] = [min(hit["box"][0], w["box"][0]), min(hit["box"][1], w["box"][1]),
                      max(hit["box"][2], w["box"][2]), max(hit["box"][3], w["box"][3])]
        if w["points"] > hit["score"]:
            hit.update(score=w["points"], reasons=w["reasons"])
    for hit in by_line.values():
        hit["box"] = [round(v / scale, 1) for v in hit["box"]]
        result["suspicious"].append(hit)
    if debug:
        result["words"] = words
    return result
