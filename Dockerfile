FROM python:3.12-slim-bookworm
COPY --from=ghcr.io/astral-sh/uv:0.7.19 /uv /uvx /bin/

ENV TRANSFORMERS_CACHE=/cache/huggingface

WORKDIR /backend
ENV PORT=8000

# 先に依存関係をインストールしておくと、毎回のインストールにならない
COPY requirements.txt .
# pipの機能のキャッシュではなく、Dockerのコマンドベースのキャッシュを行うのでこちらは--no-cache-dirをつける
RUN uv pip install --no-cache-dir -r requirements.txt --system --verbose

# WORKDIRで指定しているので二つ目の.が/backendを指す
COPY . .
# 環境変数を使用するためにsh -cを使用
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port $PORT"]