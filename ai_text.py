import os, textwrap, requests

def _have_ai():
    return bool(os.getenv("OPENAI_API_KEY","").strip())

def _chat(system, user, max_tokens=320, temperature=0.4):
    url = "https://api.openai.com/v1/chat/completions"
    r = requests.post(
        url,
        headers={"Authorization": f"Bearer {os.getenv('OPENAI_API_KEY').strip()}"},
        json={
            "model": "gpt-4o-mini",
            "temperature": temperature,
            "max_tokens": max_tokens,
            "messages": [
                {"role":"system","content":system},
                {"role":"user","content":user},
            ],
        },
        timeout=60
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]

def maybe_generate_texts(cand: dict, title_max_len: int = 60) -> dict:
    """
    Si hay OPENAI_API_KEY, genera título (<=60), bullets, descripción y garantía.
    Si no, deja las semillas y un título podado.
    """
    if not _have_ai():
        seed = (cand.get("title_seed") or "Product").strip()
        cand["title"] = seed[:title_max_len]
        if not cand.get("warranty"):
            cand["warranty"] = "30-day limited warranty"
        return cand

    sys = ("You write concise, high-converting ecommerce copy in English for Mercado Libre Global Selling (CBT). "
           "Titles MUST be <= {max_len} characters and include brand/model when present. Avoid claims and HTML.".format(max_len=title_max_len))
    feats = "\n".join([f"- {b}" for b in (cand.get("bullets_seed") or [])[:5]])
    user = f"""
Brand: {cand.get('brand') or 'N/A'}
Model: {cand.get('model') or 'N/A'}
Title seed: {cand.get('title_seed') or ''}
Key features:
{feats}

Write:
1) EXACT title (<= {title_max_len} chars), include brand/model if present.
2) 4 short bullet points.
3) 4–6 sentence plain-text description (no HTML).
4) One-line vague warranty (e.g., "30-day limited warranty").
"""

    content = _chat(sys, user, max_tokens=420)
    lines = [l.strip() for l in content.splitlines() if l.strip()]

    # title
    t = next((l for l in lines if 10 <= len(l) <= title_max_len), (cand.get("title_seed") or "Product")[:title_max_len])
    cand["title"] = " ".join(t.split())

    # bullets
    bullets = [l.lstrip("-• ").strip() for l in lines if l.startswith(("-", "•"))][:4]
    if len(bullets) < 4:
        bullets += ["Feature"] * (4 - len(bullets))

    # description
    descr_lines = [l for l in lines if l not in bullets and l != t]
    desc = "\n".join(descr_lines) or cand.get("description") or ""
    cand["highlights"] = bullets
    cand["description"] = textwrap.shorten(desc.replace("\r",""), width=3000, placeholder="…")
    cand["warranty"] = "30-day limited warranty"
    return cand