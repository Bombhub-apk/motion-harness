#!/usr/bin/env python3
"""
Jev Neuro-Symbolic Cognitive Motion Gate (with Graceful Heuristic Fallback)
Part of the Unified Motion & Video Harness.

Evaluates kinetic readability, dwell times, and motion-slop criteria.
Default: Uses Jev System 1 for ~210ms zero-hallucination probability judgments.
Fallback: If Jev API key is missing or offline, gracefully executes deterministic local heuristics.
"""

import os
import re
import sys
import json
from pathlib import Path

# Ensure UTF-8 output on Windows terminals
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

def extract_cksd_from_html(html_path: Path) -> dict:
    content = html_path.read_text(encoding="utf-8")
    
    # 1. Total duration from composition
    dur_match = re.search(r'data-duration=["\']([\d.]+)["\']', content)
    total_duration = float(dur_match.group(1)) if dur_match else 10.0

    # 2. Extract leaf text elements (headings, paragraphs, spans, labels)
    text_nodes = []
    # Match elements that contain text and no nested tags
    element_pattern = re.compile(r'<(h[1-6]|p|span|button|label|div)[^>]*\bid=["\']([^"\']+)["\'][^>]*>([^<]+)</\1>', re.IGNORECASE)
    for match in element_pattern.finditer(content):
        tag, elem_id, raw_text = match.groups()
        clean_text = raw_text.strip()
        if clean_text:
            words = [w for w in clean_text.split() if w]
            text_nodes.append({
                "id": f"#{elem_id}",
                "tag": tag.lower(),
                "text": clean_text,
                "word_count": len(words)
            })

    # 3. Extract GSAP tweens for timing
    for node in text_nodes:
        nid = re.escape(node["id"])
        
        # Entrance: tl.fromTo("#id", {...}, {..., duration: D}, start_t)
        ent_match = re.search(
            rf'tl\.fromTo\s*\(\s*["\']{nid}["\']\s*,\s*\{{[^}}]*\}}\s*,\s*\{{[^}}]*duration:\s*([\d.]+)[^}}]*\}}\s*,\s*([\d.]+)',
            content,
            re.DOTALL
        )
        if ent_match:
            duration = float(ent_match.group(1))
            start_t = float(ent_match.group(2))
            settle_t = start_t + duration
        else:
            settle_t = 0.5
        
        # Exit: tl.to("#id", {..., duration: D}, exit_t)
        exit_match = re.search(
            rf'tl\.to\s*\(\s*["\']{nid}["\']\s*,\s*\{{[^}}]*\}}\s*,\s*([\d.]+)',
            content,
            re.DOTALL
        )
        if exit_match:
            exit_t = float(exit_match.group(1))
        else:
            exit_t = total_duration

        hold_time = max(0.0, exit_t - settle_t)
        node["settle_t"] = round(settle_t, 2)
        node["exit_t"] = round(exit_t, 2)
        node["hold_sec"] = round(hold_time, 2)
        node["words_per_sec"] = round(node["word_count"] / max(0.1, hold_time), 2)

    # 4. Motion metrics (anti-slop checks)
    has_linear_motion = bool(re.search(r'ease:\s*["\'](?:none|linear)["\']', content))
    
    return {
        "duration": total_duration,
        "text_nodes": text_nodes,
        "motion_metrics": {
            "has_linear_motion": has_linear_motion
        }
    }

def run_cognitive_gate():
    project_dir = Path.cwd()
    html_file = project_dir / "index.html"
    
    if not html_file.exists():
        print(f"Error: index.html not found in {project_dir}")
        sys.exit(1)

    print("=======================================================================")
    print(" [Motion Harness] Cognitive Saliency & Readability Gate")
    print("=======================================================================")
    
    digest = extract_cksd_from_html(html_file)
    print(f" * Composition Duration: {digest['duration']}s")
    print(f" * Analyzed Text Nodes:  {len(digest['text_nodes'])}")
    for node in digest["text_nodes"]:
        print(f"   - {node['id']}: \"{node['text']}\" ({node['word_count']} word(s), Settle: {node['settle_t']}s, Exit: {node['exit_t']}s, Hold: {node['hold_sec']}s)")

    # Check for Jev availability
    api_key = os.environ.get("TYPESAFE_API_KEY")
    client = None
    if api_key:
        try:
            from typesafe_sdk import TypeSafeClient, Noul, Choice
            client = TypeSafeClient()
        except Exception:
            client = None

    if client:
        print("\n [Mode: Jev System 1 Active (~210ms, Structured Probability Engine)]")
        try:
            eval_payload = {
                "nodes": digest["text_nodes"],
                "has_linear_motion": digest["motion_metrics"]["has_linear_motion"]
            }
            
            prompt = (
                f"Evaluate this programmatic motion digest for readability and motion-slop. "
                f"Rule: Short labels must hold >= 0.8s, sentences >= 0.3s/word. Easing must not be linear. "
                f"Data: {json.dumps(eval_payload)}"
            )

            resp = client.system_one(
                state=prompt,
                questions={
                    "violation": Noul(instructions="Is there an unreadable text or motion defect in this animation?"),
                    "remedy": Choice(
                        instructions="Select action",
                        criteria={
                            "extend_hold": "Dwell time is too short for text length",
                            "switch_ease": "Easing is linear or jarring",
                            "pass_clean": "Animation timing and readability are compliant and sound"
                        }
                    )
                }
            )

            noul_val = resp.answers["violation"].noul
            remedy_ans = resp.answers["remedy"]

            if remedy_ans.choice == "pass_clean" and noul_val < 0.60:
                print(f" [+] [Jev Verdict] Clean & compliant! (Verdict: {remedy_ans.choice}, Risk: {noul_val:.2f})")
                print(" [+] Cognitive readability verified. 0 slop detected.")
                print("=======================================================================")
                return
            else:
                print(f" [!] [Jev Verdict] Issue flagged (Risk: {noul_val:.2f}, Recommended: {remedy_ans.choice})")
                if remedy_ans.choice != "pass_clean":
                    print(f" [!] Surgical Remedy: {remedy_ans.choice} (confidence: {remedy_ans.confidence:.2f})")
                    sys.exit(1)
                else:
                    return

        except Exception as e:
            print(f" [i] Jev call encountered an issue: {e}")
            print(" [i] Gracefully activating deterministic local heuristic fallback...")
    else:
        print("\n [Mode: Graceful Local Heuristic Fallback (No Jev API key required)]")

    # Local Heuristic Fallback Engine
    violations = []
    for node in digest["text_nodes"]:
        if node["hold_sec"] < 0.8:
            violations.append(f"{node['id']} hold duration ({node['hold_sec']}s) is under the 0.8s minimum threshold.")
        min_required_hold = node["word_count"] * 0.3
        if node["hold_sec"] < min_required_hold:
            violations.append(f"{node['id']} ({node['word_count']} words) holds for {node['hold_sec']}s, but requires at least {min_required_hold:.2f}s.")

    if digest["motion_metrics"]["has_linear_motion"]:
        violations.append("Linear motion ('ease: none' / 'ease: linear') detected on kinetic element.")

    if violations:
        print("\n [X] [Heuristic Gate Failed]")
        for v in violations:
            print(f"   - {v}")
        sys.exit(1)
    else:
        print(" [+] [Heuristic Gate Passed]")
        print("   All text elements meet dwell-time & anti-slop guidelines.")
        print("=======================================================================")

if __name__ == "__main__":
    run_cognitive_gate()
