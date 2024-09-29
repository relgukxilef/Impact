# This Python file uses the following encoding: utf-8
import sys
from pathlib import Path
from threading import Thread, Semaphore
import urllib.parse
import time
import tempfile

from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtCore import QObject, QSize, Slot, Property
from PySide6.QtMultimedia import QVideoFrame, QVideoFrameFormat, QVideoSink
import av

def smpte_timecode(total_seconds):
    hours, total_seconds = divmod(total_seconds, 3600)
    minutes, total_seconds = divmod(total_seconds, 60)
    seconds, total_seconds = divmod(total_seconds, 1)
    total_seconds = total_seconds * 100
    return (
        f'{hours:02.0f}:{minutes:02.0f}:{seconds:02.0f}.{total_seconds:02.0f}'
    )

should_exit = False

video_sink = None

class Model(QObject):
    @Slot(str, QObject)
    def drop(self, path, video_output):
        global video_sink
        create_subtitles.next_video = urllib.parse.unquote(
            urllib.parse.urlparse(path).path
        )[1:]
        create_subtitles.semaphore.release()
        video_sink = video_output.property("videoSink")
        

def create_subtitles():
    # TODO: using function attributes could cause a race condition
    create_subtitles.semaphore = Semaphore(0)
    create_subtitles.next_video = None
    global should_exit

    import whisper
    model = whisper.load_model("tiny")#"small")

    video = None

    while not should_exit:
        while video == create_subtitles.next_video:
            create_subtitles.semaphore.acquire()
        video = create_subtitles.next_video

        segments = model.transcribe(
            video, verbose=False, word_timestamps=True
        )["segments"]

        ass = tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False)

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

        export_videos.video = video
        export_videos.ass = ass
        export_videos.semaphore.release()


def export_videos():
    export_videos.semaphore = Semaphore(0)
    export_videos.ass = None
    export_videos.video = None

    video = None

    while not should_exit:
        while video == export_videos.video:
            export_videos.semaphore.acquire()
        video = export_videos.video
        ass = export_videos.ass

        file = av.open(video)
        video_stream = file.streams.video[0]
        width = video_stream.width
        height = video_stream.height
        frame_rate = video_stream.average_rate
        duration = video_stream.duration * video_stream.time_base

        output = av.open("output.webm", mode="w")
        stream = output.add_stream("vp9")
        
        graph = av.filter.Graph()
        filters = [
            graph.add(
               "color", color="0x00000000", size=f"{width}x{height}", 
                rate=f"{frame_rate}", 
                duration=f"{duration.numerator / duration.denominator}",
            ),
            graph.add("subtitles", filename=ass.name),
            graph.add("buffersink"),
        ]
        for filter in zip(filters[:-1], filters[1:]):
            filter[0].link_to(filter[1])
        
        graph.configure()

        #while video == export_videos.video and not should_exit:
        while True:
            try:
                for packet in stream.encode(graph.pull()):
                    output.mux(packet)
            except (av.BlockingIOError, av.EOFError):
                break

        continue

        frame = QVideoFrame(
            QVideoFrameFormat(
                QSize(width, height), 
                QVideoFrameFormat.PixelFormat.Format_ARGB8888
            )
        )
        assert frame.map(QVideoFrame.MapMode.WriteOnly)
        #bits = process.stdout.read(width * height * 4)

        #frame.bits(0)[:] = bits
        frame.unmap()
        frame.setStartTime(0)
        frame.setEndTime(1000*1000)

        video_sink.setVideoFrame(frame)
        # TODO: avoid drift
        time.sleep(frame_rate.numerator / frame_rate.denominator)

if __name__ == "__main__":
    model = Model()

    threads = [
        Thread(target=task) for task in [create_subtitles, export_videos]
    ]
    for thread in threads:
        thread.start()

    app = QGuiApplication(sys.argv)
    engine = QQmlApplicationEngine()
    qml_file = Path(__file__).resolve().parent / "main.qml"
    engine.setInitialProperties({"model": model})
    engine.load(qml_file)
    if not engine.rootObjects():
        sys.exit(-1)
    result = app.exec()

    should_exit = True
    create_subtitles.semaphore.release()
    export_videos.semaphore.release()

    for thread in threads:
        thread.join()

    sys.exit(result)
