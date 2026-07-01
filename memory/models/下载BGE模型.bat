@echo off
echo 正在从国内镜像下载 BGE 模型...
set HF_ENDPOINT=https://hf-mirror.com
python -c "from huggingface_hub import snapshot_download; snapshot_download('BAAI/bge-small-zh-v1.5', local_dir=r'D:\0.个人文档\个人文档\启元智能\brain\memory\models\bge-small-zh-v1.5')"
echo 下载完成！
pause