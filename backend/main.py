import os
import json
import tempfile
import re
from pathlib import Path
from typing import List

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, File, UploadFile, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

import anthropic
import pdfplumber
import docx

from system_prompt import SYSTEM_PROMPT

# ── Config ──────────────────────────────────────────────────────
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:8080")
PORT = int(os.getenv("PORT", 3001))
MAX_FILE_SIZE = 20 * 1024 * 1024   # 20 MB
MAX_FILES = 5
MAX_CHARS_PER_DOC = 80_000
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}

# ── App ──────────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="One Pager Liqi — API")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # restrinja para FRONTEND_ORIGIN em produção
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

claude = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


# ── Document parsing ─────────────────────────────────────────────
def parse_pdf(path: str) -> str:
    text = ""
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                text += t + "\n"
    return text


def parse_docx(path: str) -> str:
    doc = docx.Document(path)
    return "\n".join(p.text for p in doc.paragraphs)


def parse_txt(path: str) -> str:
    return Path(path).read_text(encoding="utf-8", errors="replace")


def sanitize(text: str) -> str:
    text = text.replace("\x00", "")
    text = re.sub(r"\r\n|\r", "\n", text)
    text = re.sub(r"\n{4,}", "\n\n\n", text)
    return text.strip()


def extract_text(path: str, filename: str) -> str:
    ext = Path(filename).suffix.lower()
    if ext == ".pdf":
        text = parse_pdf(path)
    elif ext == ".docx":
        text = parse_docx(path)
    elif ext == ".txt":
        text = parse_txt(path)
    else:
        raise ValueError(f"Formato não suportado: {ext}")

    text = sanitize(text)
    if len(text) > MAX_CHARS_PER_DOC:
        text = text[:MAX_CHARS_PER_DOC] + "\n[... texto truncado por limite de contexto ...]"
    return text


# ── Claude agent ─────────────────────────────────────────────────
def call_claude(documents: list[dict]) -> dict:
    docs_section = "\n\n".join(
        f"=== DOCUMENTO {i+1}: {d['name']} ===\n{d['text']}"
        for i, d in enumerate(documents)
    )

    user_prompt = (
        "Analise os documentos abaixo e extraia as informações para preencher o JSON "
        "do One Pager da Liqi Digital Assets.\n\n"
        f"DOCUMENTOS FORNECIDOS:\n{docs_section}\n\n"
        "Retorne APENAS o JSON estruturado conforme o schema especificado no system prompt. "
        "Nenhum texto adicional."
    )

    message = claude.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=8096,
        temperature=0,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )

    raw = message.content[0].text.strip()
    return parse_json(raw)


def parse_json(raw: str) -> dict:
    # Tenta direto
    try:
        return json.loads(raw)
    except Exception:
        pass
    # Tenta extrair ```json ... ```
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except Exception:
            pass
    # Tenta primeiro { ... } completo
    start, end = raw.find("{"), raw.rfind("}")
    if start != -1 and end != -1:
        try:
            return json.loads(raw[start:end + 1])
        except Exception:
            pass
    raise ValueError("Não foi possível parsear a resposta do Claude como JSON válido.")


# ── Routes ───────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/extract")
@limiter.limit("10/minute")
async def extract(request: Request, documents: List[UploadFile] = File(...)):
    if not documents:
        raise HTTPException(status_code=400, detail="Nenhum documento enviado.")
    if len(documents) > MAX_FILES:
        raise HTTPException(status_code=400, detail=f"Máximo de {MAX_FILES} arquivos por requisição.")

    parsed_docs = []
    tmp_files = []

    try:
        for upload in documents:
            ext = Path(upload.filename).suffix.lower()
            if ext not in ALLOWED_EXTENSIONS:
                raise HTTPException(status_code=400, detail=f"Formato não suportado: {upload.filename}")

            content = await upload.read()
            if len(content) > MAX_FILE_SIZE:
                raise HTTPException(status_code=400, detail=f"Arquivo muito grande: {upload.filename}")

            # Salvar temporariamente
            suffix = ext
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(content)
                tmp_files.append(tmp.name)

            text = extract_text(tmp_files[-1], upload.filename)
            parsed_docs.append({"name": upload.filename, "text": text})

        result = call_claude(parsed_docs)
        return {"success": True, "data": result}

    except HTTPException:
        raise
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})
    finally:
        for path in tmp_files:
            try:
                os.unlink(path)
            except Exception:
                pass


# ── Entry point ──────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=PORT, reload=True)
