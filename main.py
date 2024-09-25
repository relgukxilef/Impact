# This Python file uses the following encoding: utf-8
import sys
from pathlib import Path
from threading import Thread, Semaphore
import urllib.parse
import tempfile

from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtCore import QObject, QSize, Slot
from PySide6.QtMultimedia import QVideoFrame, QVideoFrameFormat, QVideoSink
import ffmpeg

def smpte_timecode(total_seconds):
    hours, total_seconds = divmod(total_seconds, 3600)
    minutes, total_seconds = divmod(total_seconds, 60)
    seconds, total_seconds = divmod(total_seconds, 1)
    total_seconds = total_seconds * 100
    return (
        f'{hours:02.0f}:{minutes:02.0f}:{seconds:02.0f}.{total_seconds:02.0f}'
    )

should_exit = False
work_semaphore = Semaphore(0)
next_video = None

video_output = None

class Model(QObject):
    @Slot(str, QObject)
    def drop(self, path, next_video_output):
        global next_video, work_semaphore
        next_video = urllib.parse.unquote(urllib.parse.urlparse(path).path)[1:]
        work_semaphore.release()
        video_output = next_video_output


def work():
    global next_video, work_semaphore, should_exit
    import whisper
    model = whisper.load_model("tiny")#"small")

    video = None

    while not should_exit:
        work_semaphore.acquire()
        if video == next_video:
            continue
        video = next_video

        segments = model.transcribe(
            video, verbose=False, word_timestamps=True
        )["segments"]

        ass = open("subtitles.ass", "w", encoding="utf-8")

        ass.write(
            "[Script Info]\n"
            "Title: assa-sample\n"
            "ScriptType: v4.00+\n"
            "PlayDepth: 0\n"
            "ScaledBorderAndShadow: Yes\n"
            "\n"
            "[V4+ Styles]\n"
            "Format: Name, Fontname, Fontsize, PrimaryColour, "
            "SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
            "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
            "BorderStyle, Outline, Shadow, "
            "Alignment, MarginL, MarginR, MarginV, Encoding\n"
            "Style: Default,Arial,80,&H00FFFFFF,&H0000FFFF,&H00000000,"
            "&H00000000,"
            "0,0,0,0,100,100,0,0,1,1,1,5,10,10,10,1\n"
            "\n"
            "[Events]\n"
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, "
            "MarginV, Effect, Text\n"
        )

        for segment in segments:
            for word in segment["words"]:
                start = smpte_timecode(word["start"])
                end = smpte_timecode(word["end"])
                text = word["word"].strip()
                ass.write(
                    f"Dialogue: 0,{start},{end},Default,,0,0,0,,{text}\n"
                )

        ass.close()

        meta = ffmpeg.probe(video)["streams"][0]
        width, height = meta["width"], meta["height"]

        process = ffmpeg.input(video).filter(
            # shit library fucks up escaping, so no arguments with : or \ work
            "subtitles", "subtitles.ass"
        ).output(
            #'pipe:', format='rawvideo', pix_fmt='argb'
            'output.mp4'
        ).run()

        continue

        frame = QVideoFrame(
            QVideoFrameFormat(
                QSize(width, height), 
                QVideoFrameFormat.PixelFormat.Format_ARGB8888
            )
        )
        assert frame.map(QVideoFrame.MapMode.WriteOnly)
        frame.bits(0)[:] = process.stdout.read(width * height * 4)
        frame.setStartTime(0)
        frame.setEndTime(1000*1000)
        frame.unmap()

        #video_sink.setVideoFrame(frame)

if __name__ == "__main__":
    model = Model()

    worker = Thread(target=work)
    worker.start()

    app = QGuiApplication(sys.argv)
    engine = QQmlApplicationEngine()
    qml_file = Path(__file__).resolve().parent / "main.qml"
    engine.setInitialProperties({"model": model})
    engine.load(qml_file)
    if not engine.rootObjects():
        sys.exit(-1)
    result = app.exec()

    should_exit = True
    work_semaphore.release()

    worker.join()

    sys.exit(result)
