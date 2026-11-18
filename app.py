import os
import shutil
import tempfile
import urllib.parse
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
import yt_dlp

app = FastAPI()

# 允許 GitHub Pages 網頁跨域呼叫
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class DownloadReq(BaseModel):
    url: str
    format: str = "MP3"  # "MP3" or "MP4"

def cleanup_temp_dir(dir_path: str):
    """傳送完畢後立即刪除整個暫存資料夾，確保雲端空間永遠歸零"""
    try:
        if os.path.exists(dir_path):
            shutil.rmtree(dir_path, ignore_errors=True)
    except Exception:
        pass

@app.get("/")
def health():
    return {"status": "MyTube Cloud Engine Ready (Auto-Clean Enabled)"}

@app.post("/fetch")
def fetch_media(req: DownloadReq, background_tasks: BackgroundTasks):
    tmp_dir = tempfile.mkdtemp(prefix="mytube_")
    is_mp3 = req.format.upper() == "MP3"

    ydl_opts = {
        "format": "bestaudio[ext=m4a]/bestaudio/best" if is_mp3 else "best[ext=mp4]/best",
        "outtmpl": os.path.join(tmp_dir, "%(title)s.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(req.url, download=True)
            title = info.get("title", "media")
            filepath = ydl.prepare_filename(info)

        if not os.path.exists(filepath):
            cleanup_temp_dir(tmp_dir)
            raise HTTPException(status_code=500, detail="下載檔案產生失敗")

        ext = os.path.splitext(filepath)[1]
        safe_name = urllib.parse.quote(f"{title}{ext}")
        media_type = "audio/mp4" if is_mp3 else "video/mp4"

        # 註冊背景任務：檔案傳給 iPhone 後立刻清空暫存區
        background_tasks.add_task(cleanup_temp_dir, tmp_dir)

        return FileResponse(
            path=filepath,
            media_type=media_type,
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{safe_name}",
                "X-Media-Title": urllib.parse.quote(title),
                "Access-Control-Expose-Headers": "X-Media-Title, Content-Disposition"
            }
        )
    except Exception as e:
        cleanup_temp_dir(tmp_dir)
        raise HTTPException(status_code=400, detail=str(e))
