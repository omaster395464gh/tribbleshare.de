#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import glob
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional, List
import requests


def die(msg: str, code: int = 2) -> None:
    raise SystemExit(f"ERROR: {msg}")

def slugify_tag(name: str) -> str:
    # Mealie-slug ist meist einfach lower + '-' statt spaces; reicht als Fallback
    return (
        name.strip()
            .lower()
            .replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
            .replace(" ", "-")
    )

def try_load_dotenv(dotenv_path: Path) -> None:
    """Simple .env loader (no dependency). Does not override existing env vars."""
    if not dotenv_path.exists():
        return
    for raw in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v


def load_json_any(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def normalize_recipe(obj: Any) -> Dict[str, Any]:
    """
    Accepts:
      - dict (ok)
      - list (takes first dict element)
      - str (tries json.loads(str))
    Returns dict or raises.
    """
    if isinstance(obj, dict):
        return obj

    if isinstance(obj, list):
        # take first dict-like element
        for item in obj:
            if isinstance(item, dict):
                return item
        die("JSON is a list but contains no object/dict recipe.")

    if isinstance(obj, str):
        s = obj.strip()
        try:
            decoded = json.loads(s)
        except Exception as e:
            die(f"JSON is a string but not valid JSON inside: {e}")
        return normalize_recipe(decoded)

    die(f"Unsupported JSON root type: {type(obj).__name__}")


def ensure_tag(recipe: Dict[str, Any], tag_name: str) -> Dict[str, Any]:
    tags = recipe.get("tags")

    if tags is None:
        recipe["tags"] = [{"name": tag_name}]
        return recipe

    # list[str]
    if isinstance(tags, list) and (len(tags) == 0 or isinstance(tags[0], str)):
        if tag_name not in tags:
            tags.append(tag_name)
        recipe["tags"] = tags
        return recipe

    # list[dict]
    if isinstance(tags, list):
        names = set()
        for t in tags:
            if isinstance(t, dict):
                n = t.get("name")
                if isinstance(n, str):
                    names.add(n)
        if tag_name not in names:
            tags.append({"name": tag_name})
        recipe["tags"] = tags
        return recipe

    # unknown -> overwrite safely
    recipe["tags"] = [{"name": tag_name}]
    return recipe


def infer_pdf_for_json(json_path: Path, pdf_dir: Path) -> Path:
    pdf_path = pdf_dir / f"{json_path.stem}.pdf"
    if not pdf_path.exists():
        die(f"PDF not found for {json_path.name}: expected {pdf_path}")
    return pdf_path


class MealieClient:
    def __init__(self, base_url: str, token: str, timeout: int = 60):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout

    def _url(self, path: str) -> str:
        if not path.startswith("/"):
            path = "/" + path
        return self.base_url + path

    def _headers_json(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def _headers_auth(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
        }

    def create_from_html_or_json(self, recipe_obj: Dict[str, Any]) -> Any:
        """
        Mealie endpoint:
          POST /api/recipes/create/html-or-json
          returns either:
            - a slug string, e.g. "zucchini-..."
            - or a JSON object (varies by version)
        """
        payload = {
            "includeTags": False,
            "data": json.dumps(recipe_obj, ensure_ascii=False),
        }
        r = requests.post(
            self._url("/api/recipes/create/html-or-json"),
            headers=self._headers_json(),
            json=payload,
            timeout=self.timeout,
        )
        if r.status_code >= 300:
            die(f"Create failed: HTTP {r.status_code} - {r.text[:800]}")

        # Try JSON first; if it's a JSON string, requests returns python str
        try:
            return r.json()
        except Exception:
            # fallback: plain text response (slug)
            return r.text.strip().strip('"')

    def get_tag_by_slug(self, slug: str) -> dict:
        r = requests.get(self._url("/api/organizers/tags"), headers=self._headers_auth(),
                         timeout=self.timeout)
        if r.status_code >= 300:
            die(f"GET tags failed: HTTP {r.status_code} - {r.text[:500]}")
        items = r.json()
        if isinstance(items, dict) and "items" in items:
            items = items["items"]
        for t in items:
            if isinstance(t, dict) and t.get("slug") == slug:
                return t
        die(f"Tag slug '{slug}' not found")

    def patch_tags(self, recipe_slug: str, tag_obj: dict) -> None:
        payload = {"tags": [{
            "id": tag_obj.get("id"),
            "name": tag_obj.get("name"),
            "slug": tag_obj.get("slug"),
        }]}
        r = requests.patch(self._url(f"/api/recipes/{recipe_slug}"), headers=self._headers_json(),
                           json=payload, timeout=self.timeout)
        if r.status_code >= 300:
            print(f"WARNING: tag PATCH failed for {recipe_slug}: HTTP {r.status_code} - {r.text[:300]}")

    def upload_pdf_asset(self, recipe_slug: str, pdf_path: Path) -> None:
        url = self._url(f"/api/recipes/{recipe_slug}/assets")

        name = pdf_path.name
        extension = pdf_path.suffix.lstrip(".").lower() or "pdf"
        icon = "file-text"  # gängiger Default; notfalls "file"

        with pdf_path.open("rb") as f:
            files = {
                # WICHTIG: Feldname "file" wie im Browser-Beispiel
                "file": (pdf_path.name, f, "application/pdf"),
            }
            data = {
                # WICHTIG: Metadaten, die dein 422 fordert
                "name": name,
                "icon": icon,
                "extension": extension,
            }

            r = requests.post(
                url,
                headers=self._headers_auth(),  # KEIN Content-Type setzen! requests macht boundary
                files=files,
                data=data,
                timeout=self.timeout,
            )

        if r.status_code >= 300:
            die(f"PDF upload failed: HTTP {r.status_code} - {r.text[:800]}")

def pick_slug_or_id(resp: Any) -> Optional[str]:
    # If API returns slug directly
    if isinstance(resp, str):
        s = resp.strip().strip('"')
        return s or None

    if not isinstance(resp, dict):
        return None

    for k in ("slug", "id"):
        v = resp.get(k)
        if isinstance(v, str) and v:
            return v

    for wrap in ("recipe", "data", "item"):
        obj = resp.get(wrap)
        if isinstance(obj, dict):
            for k in ("slug", "id"):
                v = obj.get(k)
                if isinstance(v, str) and v:
                    return v

    return None


def main() -> None:
    ap = argparse.ArgumentParser(description="Mealie 3.11 import via /api/recipes/create/html-or-json + tag + pdf asset")
    ap.add_argument("--dotenv", default=".env", help="Path to .env (default: .env)")
    ap.add_argument("--out-json-dir", default="inbox/out_json")
    ap.add_argument("--pdf-dir", default="inbox/ocr_pdfs")
    ap.add_argument("--tag", default="NDR")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--apply", action="store_true")

    sub = ap.add_subparsers(dest="cmd", required=True)
    p1 = sub.add_parser("one")
    p1.add_argument("json_file")
    p2 = sub.add_parser("batch")
    p2.add_argument("--glob", default="ocr*.json")

    args = ap.parse_args()

    # load .env
    try_load_dotenv(Path(args.dotenv))

    base_url = os.environ.get("MEALIE_BASE_URL") or os.environ.get("MEALIE_URL") or "http://localhost:9925"
    token = os.environ.get("MEALIE_TOKEN")

    do_apply = bool(args.apply) and not bool(args.dry_run)
    if not do_apply:
        args.dry_run = True

    if do_apply and not token:
        die("MEALIE_TOKEN missing (set it in .env or env var).")

    out_dir = Path(args.out_json_dir)
    pdf_dir = Path(args.pdf_dir)

    if args.cmd == "one":
        json_paths = [Path(args.json_file)]
    else:
        json_paths = [Path(p) for p in glob.glob(str(out_dir / args.glob))]
        json_paths.sort()

    if not json_paths:
        die("No JSON files found.")

    print(f"Mealie Base URL: {base_url}")
    print(f"Mode: {'APPLY' if do_apply else 'DRY-RUN'}")
    print(f"Count: {len(json_paths)}")
    print("")

    client = MealieClient(base_url=base_url, token=token or "DRY_RUN")


    ok = failed = 0
    for jp in json_paths:
        try:
            raw = load_json_any(jp)
            recipe = normalize_recipe(raw)
            recipe = ensure_tag(recipe, args.tag)
            pdf_path = infer_pdf_for_json(jp, pdf_dir)

            title = recipe.get("name") or recipe.get("title") or jp.name
            print(f"==> {jp.name} ({title})")
            print(f"    PDF: {pdf_path.name}")
            print(f"    Tag: {args.tag}")

            if args.dry_run and not do_apply:
                print("    DRY-RUN: would POST html-or-json, PATCH tags, upload PDF\n")
                ok += 1
                continue

            created = client.create_from_html_or_json(recipe)
            slug_or_id = pick_slug_or_id(created)
            if not slug_or_id:
                die(f"Create ok but no slug/id in response: {type(created).__name__} {str(created)[:200]}")

            tag = client.get_tag_by_slug("ndr")  # exakt wie im Browser
            client.patch_tags(slug_or_id, tag)

            # asset
            client.upload_pdf_asset(slug_or_id, pdf_path)

            print(f"    OK: {slug_or_id}\n")
            ok += 1

        except Exception as e:
            print(f"    FAILED: {e}\n")
            failed += 1

    print(f"Done. OK={ok} FAILED={failed}")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()