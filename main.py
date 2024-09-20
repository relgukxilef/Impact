import whisper
import sys

sequence_number = 1

def smpte_timecode(total_seconds):
    hours, total_seconds = divmod(total_seconds, 3600)
    minutes, total_seconds = divmod(total_seconds, 60)
    seconds, total_seconds = divmod(total_seconds, 1)
    milliseconds = total_seconds * 100
    return f'{hours:02.0f}:{minutes:02.0f}:{seconds:02.0f}.{milliseconds:02.0f}'

with open("words.ass", "w", encoding="utf-8") as f:
    f.write(
        "[Script Info]\n"
        "Title: assa-sample\n"
        "ScriptType: v4.00+\n"
        "PlayDepth: 0\n"
        "ScaledBorderAndShadow: Yes\n"
        "\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        "Style: Default,Arial,80,&H00FFFFFF,&H0000FFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,1,1,2,10,10,10,1\n"
        "\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )

    model = whisper.load_model("small")

    segments = model.transcribe(sys.argv[1], word_timestamps=True)["segments"]

    for segment in segments:
        for word in segment["words"]:
            start = smpte_timecode(word["start"])
            end = smpte_timecode(word["end"])
            text = word["word"].strip()
            f.write(
                f"Dialogue: 0,{start},{end},Default,,0,0,0,,{text}\n"
            )

