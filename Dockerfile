FROM python:3.12-slim-bookworm
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV TRANSFORMERS_CACHE=/cache/huggingface

WORKDIR /backend

# 先に依存関係をインストールしておくと、毎回のインストールにならない
COPY requirements.txt .
# pipの機能のキャッシュではなく、Dockerのコマンドベースのキャッシュを行うのでこちらは--no-cache-dirをつける
RUN uv pip install --no-cache-dir -r requirements.txt --system --verbose

# WORKDIRで指定しているので二つ目の.が/backendを指す
COPY . .
# , "--log-level", "debug"でログレベルをdebugにする
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"] 