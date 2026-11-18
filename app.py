import os
import glob
import shutil
import tempfile
from urllib.parse import quote
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
import yt_dlp

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Media-Title", "Content-Disposition"],
)

class FetchRequest(BaseModel):
    url: str
    format: str = "MP3"

@app.get("/")
def health_check():
    return {"status": "ok", "service": "MyTube Cloud Engine"}

@app.post("/fetch")
def fetch_media(req: FetchRequest, background_tasks: BackgroundTasks):
    temp_dir = tempfile.mkdtemp(prefix="mytube_")
    is_mp4 = req.format.upper() == "MP4"

    ydl_opts = {
        "outtmpl": os.path.join(temp_dir, "%(title)s.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "geo_bypass": True,
        "extractor_args": {
            "youtube": {
                "player_client": ["android", "ios", "tv_embedded", "web"]
            }
        },
        "http_headers": {
            "User-Agent": "com.google.android.youtube/19.29.37 (Linux; U; Android 14; en_US) gzip"
        }
    }

    if is_mp4:
        ydl_opts["format"] = "bestvideo[ext=mp4][height<=1080]+bestaudio[ext=m4a]/best[ext=mp4]/best"
        ydl_opts["merge_output_format"] = "mp4"
    else:
        ydl_opts["format"] = "bestaudio[ext=m4a]/bestaudio/best"

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(req.url, download=True)
            title = info.get("title", "YouTube_Media")

        files = [f for f in glob.glob(os.path.join(temp_dir, "*")) if os.path.isfile(f)]
        if not files:
            raise HTTPException(status_code=500, detail="找不到下載完成的媒體檔案")

        file_path = files[0]
        ext = os.path.splitext(file_path)[1] or (".mp4" if is_mp4 else ".m4a")
        media_type = "video/mp4" if is_mp4 else "audio/mp4"
        encoded_title = quote(title)

        background_tasks.add_task(shutil.rmtree, temp_dir, True)

        return FileResponse(
            path=file_path,
            media_type=media_type,
            filename=f"{title}{ext}",
            headers={"X-Media-Title": encoded_title}
        )
    except Exception as e:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise HTTPException(status_code=400, detail=str(e))
