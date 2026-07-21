# Pixel Hopper

Losslessly encode arbitrary files and folders into sets of ordinary PNG images, then reconstruct the original data byte-for-byte — even if some of the PNGs are lost or corrupted.

Pixel Hopper stores data directly in RGB pixel values (no Base64 expansion), wraps every chunk in a self-describing manifest, and uses forward error correction (FEC) so the archive can survive missing or damaged pieces.

---

## Features

- **Lossless round-trip** — SHA256-verified encode/decode
- **Forward error correction** — reconstruct from any sufficient subset of chunks (data + parity), via `fec_layer.py`
- **Self-describing chunks** — every PNG embeds a copy of the manifest, so there's no single point of failure
- **Integrity verification** — each chunk stores its own SHA256 hash, byte length, and index; corrupted chunks are discarded before reconstruction
- **Folder support** — folders are zipped, encoded, then unzipped on decode
- **No Base64 overhead** — bytes are written directly into image pixels instead of ASCII-encoded text
- **CLI + interactive menu** — batch encode/decode uploads, or use as a library

---

## How It Works

### Encoding

```
File / Folder
      │
      ▼
   Zip (if folder)
      │
      ▼
 Split into chunks (default 50 MB)
      │
      ▼
 Forward Error Correction (fec_layer)
      │  → data chunks + parity chunks
      ▼
 Prepend manifest to each chunk
      │
      ▼
 Bytes → RGB pixel array → PNG
```

### Decoding

```
Read PNGs
      │
      ▼
 Extract raw RGB bytes
      │
      ▼
 Recover manifest
   (manifest.png, or fallback: scan chunks for a valid one)
      │
      ▼
 Verify SHA256 per chunk
      │
      ▼
 Discard corrupted / missing chunks
      │
      ▼
 Reconstruct via FEC (recover_original_bytes)
      │
      ▼
 Reassemble zip → unzip → restore file/folder
```

---

## Manifest Design

Originally, a single `*_manifest.png` was the only source of reconstruction metadata — if it was lost, nothing could be decoded.

Every chunk now stores its own manifest header:

```
[4 bytes manifest length][manifest JSON][chunk payload]
```

via `add_manifest_header()` / `remove_manifest_header()`. If the dedicated manifest PNG is missing, the decoder falls back to scanning every chunk (`extract_manifest_from_chunk`) until it finds a valid one.

---

## Installation

```bash
git clone https://github.com/ronak314/PixelVault
cd pixel-hopper
pip install numpy pillow
```

Requires Python 3.10+ (uses `dataclass(slots=True)` and `from __future__ import annotations`).

---

## Usage

### Interactive mode

Run with no arguments for a simple menu:

```bash
python pixel_hopper.py
```

```
Pixel Hopper
1) Encode every file in uploads
2) Decode every encoded set in encoded_png
3) Purge uploads, encoded_png, and reconstructed
4) Quit
```

Drop files/folders into `uploads/`, choose `1` to encode them into `encoded_png/`, and `2` to decode them back into `reconstructed/`.

### Command line

**Encode a file:**

```bash
python pixel_hopper.py encode path/to/file.bin -o output_dir --chunk-size-mb 50
```

**Decode a chunk set:**

```bash
python pixel_hopper.py decode output_dir/file.bin_manifest.png -o path/to/restored.bin
```

### As a library

```python
from pixel_hopper import encode_file_to_png, decode_png_to_file

result = encode_file_to_png("my_file.zip", output_dir="encoded_png", chunk_size=50 * 1024 * 1024)
print(result.manifest_path, result.chunk_paths)

decode_png_to_file("encoded_png/my_file.zip_manifest.png", "restored.zip")
```

---

## Directory Layout

| Directory       | Purpose                                  |
|-----------------|-------------------------------------------|
| `uploads/`      | Drop files/folders here to be encoded     |
| `encoded_png/`  | Output PNG chunk sets (manifest + shares) |
| `reconstructed/`| Decoded/restored files                    |

---

## Known Limitations

- **macOS `.app` bundles** don't launch correctly after reconstruction — likely due to lost executable permissions, invalidated code signing, quarantine attributes, or `zipfile` not preserving macOS-specific metadata. Unrelated to the PNG encoding itself; needs a zip-metadata-preservation fix.
- Chunk size is currently fixed at 50 MB by default (`Chunk_MB` in source).

---

## Project Status

Encoding, decoding, hash verification, manifest recovery, and folder restoration are all working end-to-end. Remaining work is mostly around edge cases (see Known Limitations) and possible architecture changes for the FEC layer.

---

## License

tba
