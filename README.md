# looky

# 1. イメージをビルド
docker build -t looky-backend -f Dockerfile .

# 2. コンテナを実行
docker run -d \
  --name looky-backend \
  -p 8080:8000 \
  -v $(pwd):/backend \
  --restart unless-stopped \
  looky-backend

# 2.5 コンテナを実行(Windows)
docker run --name looky-backend -p 8080:8000 -v ${PWD}:/backend --restart unless-stopped looky-backend


# コンテナを停止
docker stop looky-backend

# コンテナを削除（停止後）
docker rm looky-backend

# または、停止と削除を同時に行う場合
docker rm -f looky-backend