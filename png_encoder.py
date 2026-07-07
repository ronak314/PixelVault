"""Encode and decode binary data as RGB PNG images."""

from __future__ import annotations

import argparse
import hashlib
import math
from pathlib import Path
from typing import Sequence

import numpy as np
from PIL import Image, PngImagePlugin


def sha256_bytes(data: bytes) -> str:
    """Return the SHA256 hex digest for a bytes object."""

    return hashlib.sha256(data).hexdigest()


def sha256_file(path: str | Path) -> str:
    """Return the SHA256 hex digest for a file without loading it all at once."""

    file_path = Path(path)
    digest = hashlib.sha256()
    with file_path.open("rb") as file_handle:
        for chunk in iter(lambda: file_handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def bytes_to_rgb_array(data: bytes, width: int | None = None) -> np.ndarray:
    """Convert raw bytes into a 3-channel NumPy image array.

    Each pixel stores three consecutive bytes as RGB values. If the final pixel
    is incomplete, it is padded with zeros.

    Args:
        data: Raw binary data to encode.
        width: Optional image width in pixels. If omitted, a near-square width
            is chosen automatically.

    Returns:
        A uint8 array shaped as ``(height, width, 3)``.
    """

    if width is not None and width <= 0:
        raise ValueError("width must be positive")

    pixel_count = math.ceil(len(data) / 3) if data else 1
    if width is None:
        width = max(1, math.isqrt(pixel_count))
        while pixel_count % width != 0:
            width -= 1

    height = math.ceil(pixel_count / width)
    padded_size = height * width * 3

    buffer = np.frombuffer(data, dtype=np.uint8)
    if buffer.size < padded_size:
        buffer = np.pad(buffer, (0, padded_size - buffer.size), mode="constant")

    return buffer.reshape((height, width, 3))


def encode_bytes_to_png(
    data: bytes,
    output_path: str | Path,
    width: int | None = None,
    original_filename: str | None = None,
) -> Path:
    """Write binary data to a PNG image and return the output path.

    The original byte length is stored in PNG metadata so the data can be
    reconstructed exactly, even when the final pixel is padded with zeros.
    """

    image_array = bytes_to_rgb_array(data, width=width)
    image = Image.fromarray(image_array, mode="RGB")
    metadata = PngImagePlugin.PngInfo()
    metadata.add_text("original_length", str(len(data)))
    metadata.add_text("sha256", sha256_bytes(data))
    if original_filename:
        metadata.add_text("original_filename", original_filename)

    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_file, format="PNG", pnginfo=metadata)
    return output_file


def encode_file_to_png(input_path: str | Path, output_path: str | Path, width: int | None = None) -> Path:
    """Read a binary file and encode it as a PNG image."""

    input_file = Path(input_path)
    return encode_bytes_to_png(
        input_file.read_bytes(),
        output_path,
        width=width,
        original_filename=input_file.name,
    )


def decode_png_to_bytes(input_path: str | Path) -> bytes:
    """Reconstruct the original binary data from an encoded PNG image."""

    input_file = Path(input_path)
    with input_file.open("rb") as file_handle:
        with Image.open(file_handle) as image:
            image = image.convert("RGB")
            pixel_data = np.asarray(image, dtype=np.uint8).reshape(-1)

            original_length_text = image.info.get("original_length")
            expected_sha256 = image.info.get("sha256")
            if original_length_text is None:
                data = pixel_data.tobytes().rstrip(b"\x00")
                if expected_sha256 is not None and sha256_bytes(data) != expected_sha256:
                    raise ValueError("decoded data checksum does not match PNG metadata")
                return data

            original_length = int(original_length_text)
            data = pixel_data.tobytes()[:original_length]
            if expected_sha256 is not None and sha256_bytes(data) != expected_sha256:
                raise ValueError("decoded data checksum does not match PNG metadata")
            return data


def decode_png_to_file(input_path: str | Path, output_path: str | Path) -> Path:
    """Decode an encoded PNG image back into a binary file."""

    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_bytes(decode_png_to_bytes(input_path))
    return output_file


def decoded_filename_from_png(input_path: str | Path) -> str:
    """Return the filename stored in PNG metadata, or a safe fallback."""

    input_file = Path(input_path)
    with input_file.open("rb") as file_handle:
        with Image.open(file_handle) as image:
            original_filename = image.info.get("original_filename")
            if original_filename:
                return Path(original_filename).name
    return Path(input_file.stem).with_suffix(".bin").name


def resolve_encoded_png_path(input_path: str | Path) -> Path:
    """Resolve a decode target to the generated PNG, even from the source name.

    This lets callers pass either the encoded PNG itself or the original source
    file path; the decoder always uses the PNG in ``encoded_png``.
    """

    input_file = Path(input_path)
    if input_file.suffix.lower() == ".png" and input_file.exists():
        return input_file

    base_dir = Path(__file__).resolve().parent
    candidate = base_dir / "encoded_png" / f"{input_file.stem}.png"
    if candidate.exists():
        return candidate

    raise FileNotFoundError(f"encoded PNG not found for {input_path}")


def verify_file_round_trip(original_path: str | Path, reconstructed_path: str | Path) -> bool:
    """Compare two files by SHA256 checksum."""

    return sha256_file(original_path) == sha256_file(reconstructed_path)


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser for the encoder and decoder."""

    parser = argparse.ArgumentParser(description="Encode binary files as RGB PNG images and decode them back.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    encode_parser = subparsers.add_parser("encode", help="Encode a binary file into a PNG image.")
    encode_parser.add_argument("input_path", type=Path, help="Path to the binary input file")
    encode_parser.add_argument("-o", "--output", type=Path, help="Output PNG path")
    encode_parser.add_argument("--width", type=int, default=None, help="Optional PNG width in pixels")

    decode_parser = subparsers.add_parser("decode", help="Decode a PNG image back into a binary file.")
    decode_parser.add_argument("input_path", type=Path, help="Path to the encoded PNG file")
    decode_parser.add_argument("-o", "--output", type=Path, help="Output binary file path")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command-line interface."""

    parser = build_parser()
    args = parser.parse_args(argv)

    base_dir = Path(__file__).resolve().parent
    encoded_dir = base_dir / "encoded_png"
    reconstructed_dir = base_dir / "reconstructed"

    if args.command == "encode":
        input_checksum = sha256_file(args.input_path)
        output_path = args.output or (encoded_dir / f"{args.input_path.stem}.png")
        encode_file_to_png(args.input_path, output_path, width=args.width)
        print(f"encoded: {output_path}")
        print(f"original_sha256: {input_checksum}")
        return 0

    if args.command == "decode":
        encoded_png_path = resolve_encoded_png_path(args.input_path)
        output_path = args.output or (reconstructed_dir / decoded_filename_from_png(encoded_png_path))
        decode_png_to_file(encoded_png_path, output_path)
        original_checksum = sha256_file(args.input_path) if args.input_path.exists() and args.input_path.suffix.lower() != ".png" else None
        print(f"decoded: {output_path}")
        if original_checksum is not None:
            print(f"source_sha256: {original_checksum}")
        print(f"reconstructed_sha256: {sha256_file(output_path)}")
        return 0

    raise RuntimeError(f"unsupported command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
