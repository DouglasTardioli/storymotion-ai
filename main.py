import argparse
import logging
from pathlib import Path

from storymotion.render import render


def main():
    parser = argparse.ArgumentParser(description="StoryMotion AI — renderiza um projeto JSON")
    parser.add_argument("project", type=Path, help="Projeto JSON")
    parser.add_argument("output", type=Path, help="Vídeo MP4 de saída")
    parser.add_argument("--ffmpeg", help="Caminho para o executável do FFmpeg")
    parser.add_argument("--crf", type=int, default=20, help="Qualidade H.264 (0–51)")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        render(args.project, args.output, ffmpeg=args.ffmpeg, crf=args.crf)
    except (OSError, ValueError, RuntimeError) as error:
        logging.error("%s", error)
        return 1
    except KeyboardInterrupt:
        logging.warning("Exportação cancelada.")
        return 130
    logging.info("Vídeo exportado para %s", args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
