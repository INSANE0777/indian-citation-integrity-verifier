# Reproducible report build

The submitted PDF was built with Tectonic 0.17.0 for Windows x86_64. The compiler archive was downloaded from the official GitHub release and verified before extraction:

- Release: https://github.com/tectonic-typesetting/tectonic/releases/tag/tectonic%400.17.0
- Asset: `tectonic-0.17.0-x86_64-pc-windows-msvc.zip`
- SHA-256: `f61ce51f0b0ade1015b7de7ef368541c5424e9756ecbd0d7af97d6d48030845f`

The binary itself is intentionally not committed. With Tectonic on `PATH`:

```sh
python scripts/build_report.py
```

Or pass an explicit compiler path:

```sh
python scripts/build_report.py --tectonic C:/path/to/tectonic.exe
```

The builder regenerates `report/measurements.tex` from `results/`, checks the experiment and corpus hashes, generates the bibliography from `docs/references.json`, compiles `report/main.tex`, rejects overfull boxes and undefined references, checks for replacement glyphs and verifies a 6–7 page output. The final submitted artifact is `report/Final_Report.pdf`.

Tectonic may download TeX packages during the first build. After the packages are cached, a repeated build is offline except for any missing TeX dependency. The report does not require access to the original raw PDF cache or the Hugging Face model cache.
