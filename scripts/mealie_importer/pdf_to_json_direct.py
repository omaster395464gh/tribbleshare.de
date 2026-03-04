import json
import os
import time
from pathlib import Path
from typing import Any

import requests

INPUT_DIR = Path("inbox/ocr_pdfs")
OUTPUT_DIR = Path("inbox/out_json")

OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
MODEL = "gpt-4.1-mini"

SYSTEM_PROMPT = """
Du extrahierst exakt EIN Kochrezept aus dem Dokument.
Gib ausschließlich valides JSON zurück.
Kein Markdown. Kein Text vor oder nach dem JSON.

Schema:
{
  "@context": "https://schema.org",
  "@type": "Recipe",
  "name": "...",
  "description": "...",
  "recipeIngredient": ["..."],
  "recipeInstructions": [
    {"@type": "HowToStep", "text": "..."}
  ]
}

Falls kein Rezept erkennbar ist:
{"error":"NO_RECIPE"}
""".strip()


def openai_recipe_from_pdf_via_upload(model: str, pdf_path: str) -> Any | None:
    """
    Upload PDF -> call Responses API with file_id -> delete file.
    Returns dict (parsed JSON).
    """
    # 1) Upload
    upload_url = "https://api.openai.com/v1/files"
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}

    with open(pdf_path, "rb") as f:
        files = {"file": (os.path.basename(pdf_path), f, "application/pdf")}
        data = {"purpose": "user_data"}
        up = requests.post(upload_url, headers=headers, files=files, data=data, timeout=120)

    up.raise_for_status()
    file_id = up.json()["id"]

    try:
        # 2) Parse via Responses using file_id
        resp_url = "https://api.openai.com/v1/responses"
        headers_json = {
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": model,
            "input": [
                {
                    "role": "developer",
                    "content": SYSTEM_PROMPT,
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "input_file", "file_id": file_id},
                        {"type": "input_text", "text": "Extrahiere das Rezept gemäß Vorgaben."},
                    ],
                },
            ],
        }

        rr = requests.post(resp_url, headers=headers_json, json=payload, timeout=180)

        # Optional: bessere Fehlermeldung bei 429/402/400
        if rr.status_code >= 400:
            raise RuntimeError(f"OpenAI error {rr.status_code}: {rr.text[:1000]}")

        data = rr.json()

        # Output-Text einsammeln
        out_text = ""
        for item in data.get("output", []):
            for c in item.get("content", []):
                if c.get("type") == "output_text":
                    out_text += c.get("text", "")

        out_text = out_text.strip()
        if not out_text:
            raise RuntimeError("Empty model output")

        # JSON parsen
        try:
            return json.loads(out_text)
        except json.JSONDecodeError as e:
            # Debug-Hilfe: Output in Exception
            raise RuntimeError(f"Model returned invalid JSON: {e}\n---OUTPUT---\n{out_text[:2000]}")

    finally:
        # 3) Remove file ( the best effort)
        del_url = f"https://api.openai.com/v1/files/{file_id}"
        try:
            requests.delete(del_url, headers=headers, timeout=60)
        except Exception:
            pass


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    stats = {"OK": 0, "FAIL_NO_RECIPE": 0, "FAIL_OPENAI": 0, "FAIL_OTHER": 0}
    failures = []

    for pdf in sorted(INPUT_DIR.glob("*.pdf")):
        try:
            print(f"Verarbeite: {pdf.name}")

            result = openai_recipe_from_pdf_via_upload(MODEL, str(pdf))

            if isinstance(result, dict) and result.get("error") == "NO_RECIPE":
                stats["FAIL_NO_RECIPE"] += 1
                failures.append((pdf.name, "NO_RECIPE"))
                continue

            out_file = OUTPUT_DIR / f"{pdf.stem}.json"
            out_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

            stats["OK"] += 1

            # kleine Bremse gegen Rate Limits
            time.sleep(0.2)

        except RuntimeError as e:
            msg = str(e)
            if "OpenAI error" in msg or "Model returned invalid JSON" in msg:
                stats["FAIL_OPENAI"] += 1
                failures.append((pdf.name, msg[:300]))
            else:
                stats["FAIL_OTHER"] += 1
                failures.append((pdf.name, msg[:300]))

        except Exception as e:
            stats["FAIL_OTHER"] += 1
            failures.append((pdf.name, str(e)[:300]))

    print("\n=== SUMMARY ===")
    for k, v in stats.items():
        print(f"{k}: {v}")

    if failures:
        fail_path = OUTPUT_DIR / "_failures.json"
        fail_path.write_text(json.dumps(failures, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Fehlerliste: {fail_path}")


if __name__ == "__main__":
    main()