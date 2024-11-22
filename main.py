# This Python file uses the following encoding: utf-8

# create binary: 
#.\.venv\Scripts\pyinstaller.exe .\main.py --add-data main.qml:. --add-data .\whisper\whisper\assets\*:whisper\assets --add-binary ".\.venv\Lib\site-packages\torch\lib\torch_python.dll:torch\lib" --noconfirm

import sys
from pathlib import Path
from threading import Thread, Semaphore
import urllib.parse
import time
import tempfile

from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtCore import QObject, QSize, Slot, Property, Signal
from PySide6.QtMultimedia import QVideoFrame, QVideoFrameFormat
from PySide6.QtWidgets import QFileDialog
import numpy

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

model = None

class Model(QObject):
    progress_changed = Signal()
    label_changed = Signal()

    def __init__(self):
        super().__init__()
        self._progress = 1
        self._label = "Drop a video file here."
        #self.file_dialog = QFileDialog(self)

    @Slot(str, QObject)
    def drop(self, path, video_output):
        #self.file_dialog.open(self, lambda file: )

        global video_sink
        create_subtitles.next_video = urllib.parse.unquote(
            urllib.parse.urlparse(path).path
        )[1:]
        create_subtitles.semaphore.release()
        video_sink = video_output.property("videoSink")
        self.set_progress(0)
        self.set_label("")

    def get_progress(self):
        return self._progress
    
    def set_progress(self, value):
        self._progress = value
        self.progress_changed.emit()

    def get_label(self):
        return self._label
    
    def set_label(self, value):
        self._label = value
        self.label_changed.emit()
    
    progress = Property(float, get_progress, notify=progress_changed)
    label = Property(str, get_label, notify=label_changed)

def create_subtitles():
    # TODO: using function attributes could cause a race condition
    create_subtitles.semaphore = Semaphore(0)
    create_subtitles.next_video = None
    global should_exit
    
    import whisper
    import av

    ai = whisper.load_model("small")

    video = None

    while not should_exit:
        create_subtitles.semaphore.acquire()

        if video == create_subtitles.next_video:
            continue
        
        try:
            video = create_subtitles.next_video

            samples = []
            input = av.open(video)
            input_stream = input.streams.audio[0]
            graph = av.filter.Graph()
            filters = [
                graph.add_abuffer(template=input_stream),
                graph.add("aformat", channel_layouts="mono"),
                graph.add("aresample", "16000"),
                graph.add("abuffersink"),
            ]
            for filter in zip(filters[:-1], filters[1:]):
                filter[0].link_to(filter[1])
            
            graph.configure()

            for frame in input.decode(input_stream):
                graph.push(frame)
                samples.append(graph.pull().to_ndarray())

            samples = numpy.concatenate(samples, 1)[0]

            segments = ai.transcribe(
                samples, verbose=False, word_timestamps=True
            )["segments"]

            ass = tempfile.NamedTemporaryFile(
                "w", encoding="utf-8", delete=False
            )

            file = av.open(video)
            video_stream = file.streams.video[0]
            width = video_stream.width
            height = video_stream.height

            ass.write(
                "[Script Info]\n"
                "Title: assa-sample\n"
                "ScriptType: v4.00+\n"
                "PlayDepth: 0\n"
                "ScaledBorderAndShadow: Yes\n"
                "PlayResX: 384\n"
                f"PlayResY: {384*height//width}\n"
                "\n"
                "[V4+ Styles]\n"
                "Format: Name, Fontname, Fontsize, PrimaryColour, "
                "SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
                "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
                "BorderStyle, Outline, Shadow, "
                "Alignment, MarginL, MarginR, MarginV, Encoding\n"
                "Style: Default,Alegreya Sans SC ExtraBold,40,&H00FFFFFF,"
                "&H0000FFFF,&H00000000,"
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

        except Exception as e:
            model.set_label(f"Error: {e}")
            model.set_progress(1)

def export_videos():
    export_videos.semaphore = Semaphore(0)
    export_videos.ass = None
    export_videos.video = None
    
    import av

    global should_exit, model

    video = None

    while not should_exit:
        export_videos.semaphore.acquire()
        
        if video == export_videos.video:
            continue

        video = export_videos.video
        ass = export_videos.ass

        file = av.open(video)
        video_stream = file.streams.video[0]
        width = video_stream.width
        height = video_stream.height
        frame_rate = video_stream.average_rate
        duration = file.duration * 1e-6

        output = av.open("output.mov", mode="w")
        stream = output.add_stream("qtrle")
        stream.codec_context.width = width
        stream.codec_context.height = height
        stream.pix_fmt = "argb"
        stream.time_base = video_stream.time_base
        
        graph = av.filter.Graph()
        filters = [
            graph.add(
               "color", color="white@0.0", size=f"{width}x{height}", 
                rate=f"{frame_rate}", 
                duration=f"{duration}",
            ),
            graph.add("format", "argb"),
            graph.add("subtitles", filename=ass.name, alpha="1"),
            graph.add("buffersink"),
        ]
        for filter in zip(filters[:-1], filters[1:]):
            filter[0].link_to(filter[1])
        
        graph.configure()

        while not should_exit:
            try:
                frame = graph.pull()
                packets = stream.encode(frame)
                output.mux(packets)
                model.set_progress(
                    frame.time / duration
                )
            except (av.BlockingIOError, av.EOFError):
                break

        for packet in stream.encode(None):
            output.mux(packet)
        output.close()

        model.set_progress(1)
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
